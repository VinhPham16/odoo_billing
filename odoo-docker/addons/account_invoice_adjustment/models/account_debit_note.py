from odoo import fields, models

from .account_move import ADJUSTMENT_TYPES


class AccountDebitNote(models.TransientModel):
    """Đổ metadata điều chỉnh xuống giấy báo nợ.

    `create_debit()` của core dùng `move.copy(default=...)` chứ không phải
    `_reverse_moves()`, nên bút toán giữ nguyên chiều với hóa đơn gốc — đúng
    thứ điều chỉnh tăng cần, và là lý do luồng tăng không đi qua wizard hoàn tác.
    """

    _inherit = 'account.debit.note'

    # default=False vì cùng lý do như ở account.move.reversal: nút "Giấy báo
    # nợ" gốc vẫn dùng được (kế toán trưởng), đừng đóng dấu nhầm.
    adjustment_type = fields.Selection(
        ADJUSTMENT_TYPES, string='Loại điều chỉnh')
    adjustment_agreement_name = fields.Char(string='Văn bản thỏa thuận')
    adjustment_agreement_date = fields.Date(string='Ngày văn bản thỏa thuận')

    def _prepare_default_values(self, move):
        """Hook core -> dict đi vào move.copy() tạo GIẤY BÁO NỢ."""
        # EXTENDS 'account_debit_note'
        values = super()._prepare_default_values(move)
        if self.adjustment_type:
            values.update({
                'adjustment_type': self.adjustment_type,
                'adjustment_agreement_name': self.adjustment_agreement_name,
                'adjustment_agreement_date': self.adjustment_agreement_date,
            })
        return values
