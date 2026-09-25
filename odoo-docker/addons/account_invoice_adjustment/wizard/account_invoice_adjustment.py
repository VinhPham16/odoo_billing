from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..models.account_move import ADJUSTMENT_TYPES


class AccountInvoiceAdjustment(models.TransientModel):
    """Lớp điều phối mỏng nằm trên hai wizard core.

    KHÔNG extend `account.move.reversal`: wizard hoàn tác không phục vụ được
    điều chỉnh tăng. `TYPE_REVERSE_MAP` là dict cứng không đọc cấu hình, và
    `reversed_entry_id` là một khẳng định kế toán chứ không chỉ là link —
    `payment_state='reversed'`, bước tự đối trừ và nút "Reversed Entries" đều
    đọc nó. Ép wizard hoàn tác sinh chứng từ cùng chiều thì field đó nói dối.

    Odoo đã tách sẵn hai cơ chế: `account.move.reversal` cho bút toán ngược
    chiều, `account.debit.note` cho bút toán cùng chiều. Việc của model này chỉ
    là hỏi một câu nghiệp vụ rồi gọi đúng cái.
    """

    _name = 'account.invoice.adjustment'
    _description = 'Điều chỉnh hóa đơn'

    move_id = fields.Many2one(
        'account.move', string='Hóa đơn gốc', required=True, readonly=True)
    adjustment_type = fields.Selection(
        ADJUSTMENT_TYPES, string='Loại điều chỉnh',
        required=True, default='decrease')
    date = fields.Date(
        string='Ngày chứng từ', required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal', string='Sổ nhật ký',
        help='Để trống thì dùng sổ nhật ký của hóa đơn gốc.')
    reason = fields.Char(
        string='Lý do', required=True,
        help='In lên chứng từ điều chỉnh. TT 91/2026/TT-BTC yêu cầu ghi rõ '
             '"Điều chỉnh cho hóa đơn Mẫu số... ký hiệu... số... ngày...".')
    agreement_name = fields.Char(string='Số/tên văn bản thỏa thuận')
    agreement_date = fields.Date(string='Ngày văn bản thỏa thuận')

    # Chỉ để cảnh báo trong view trước khi người dùng bấm, không dùng để ghi.
    move_payment_state = fields.Selection(
        related='move_id.payment_state', string='Tình trạng thanh toán')
    move_is_debit_note = fields.Boolean(
        compute='_compute_move_is_debit_note')

    @api.depends('move_id')
    def _compute_move_is_debit_note(self):
        for wizard in self:
            wizard.move_is_debit_note = bool(wizard.move_id.debit_origin_id)

    def action_apply(self):
        self.ensure_one()
        move = self.move_id

        if move.state != 'posted':
            raise UserError(_('Chỉ điều chỉnh được hóa đơn đã vào sổ.'))

        # Lặp lại guard của account.debit.note.default_get. Guard đó nằm trong
        # default_get, mà _add_missing_default_values chỉ gọi default_get cho
        # field THIẾU — ở đây move_ids được truyền thẳng nên không có gì bảo
        # đảm guard chạy. Kiểm tra lại ở đây cho chắc chắn.
        if move.move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
            raise UserError(_(
                'Chỉ điều chỉnh được hóa đơn bán, hóa đơn mua, giấy báo có '
                'hoặc giấy báo nợ. Chứng từ %(name)s thuộc loại khác.',
                name=move.display_name))

        meta = {
            'adjustment_type': self.adjustment_type,
            'adjustment_agreement_name': self.agreement_name,
            'adjustment_agreement_date': self.agreement_date,
        }
        journal = self.journal_id or move.journal_id

        if self.adjustment_type == 'increase':
            # Guard thứ hai bị default_get bỏ qua. Tình huống này đã xảy ra
            # thật trong DB: RINV/2026/00007 là giấy báo có của DINV/2026/00003.
            if move.debit_origin_id:
                raise UserError(_(
                    'Chứng từ %(name)s bản thân nó đã là giấy báo nợ của một '
                    'hóa đơn khác — không lập tiếp giấy báo nợ chồng lên được. '
                    'Điều chỉnh trên hóa đơn gốc %(origin)s.',
                    name=move.display_name,
                    origin=move.debit_origin_id.display_name))

            # Bút toán CÙNG CHIỀU -> account.debit.note (move.copy).
            # copy_lines=False: nháp trống buộc kế toán gõ đúng phần chênh lệch,
            # thay vì sửa một bản sao đầy đủ và bỏ sót dòng.
            return self.env['account.debit.note'].create({
                'move_ids': [Command.set(move.ids)],
                'date': self.date,
                'reason': self.reason,
                'journal_id': journal.id,
                'copy_lines': False,
                **meta,
            }).create_debit()

        if self.adjustment_type == 'replace' and move.payment_state in (
            'paid', 'partial', 'in_payment'
        ):
            # modify_moves() -> _reverse_moves(cancel=True), và việc đầu tiên
            # core làm là lines.remove_move_reconcile(): gỡ SẠCH mọi đối trừ,
            # kể cả payment. Khoản đã thu trở thành outstanding credit trôi nổi,
            # phải nhớ gắn tay lại vào hóa đơn thay thế.
            raise UserError(_(
                'Hóa đơn %(name)s đã phát sinh thanh toán. Thay thế sẽ gỡ toàn '
                'bộ đối trừ của nó, khiến khoản đã thu trở thành khoản chưa '
                'phân bổ trôi nổi. Gỡ đối trừ thanh toán trước rồi làm lại, '
                'hoặc dùng Điều chỉnh giảm / Điều chỉnh tăng.',
                name=move.display_name))

        # decrease / info / replace -> account.move.reversal (_reverse_moves).
        # Truyền company_id thẳng thay vì trông vào default_get đọc context.
        wizard = self.env['account.move.reversal'].create({
            'move_ids': [Command.set(move.ids)],
            'company_id': move.company_id.id,
            'date': self.date,
            'journal_id': journal.id,
            'reason': self.reason,
            **meta,
        })
        # Cả hai method core đều trả sẵn window action có res_id khi chỉ một
        # move, nên return thẳng là mở đúng chứng từ vừa tạo.
        if self.adjustment_type == 'replace':
            return wizard.modify_moves()
        return wizard.refund_moves()
