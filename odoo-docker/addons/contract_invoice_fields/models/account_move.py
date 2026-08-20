from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    x_contract_number = fields.Char(string='Hợp đồng')
    x_contract_sign_date = fields.Date(string='Ngày ký')
    x_contract_effective_date = fields.Date(string='Hiệu lực')

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- Thông tin hợp đồng (đã có sẵn) ---
    x_contract_number = fields.Char(string='Hợp đồng')
    x_contract_sign_date = fields.Date(string='Ngày ký')
    x_contract_effective_date = fields.Date(string='Hiệu lực')

    # --- Trạng thái đến hạn theo từng kỳ (installment) ---
    installment_due_status = fields.Selection(
        [
            ('not_applicable', 'Không áp dụng'),
            ('not_due', 'Chưa đến hạn'),
            ('partially_due', 'Đến hạn thanh toán 1 phần'),
            ('fully_due', 'Đến hạn toàn bộ'),
            ('paid', 'Đã thanh toán đủ'),
        ],
        string='Trạng thái đến hạn',
        compute='_compute_installment_due_status',
        store=True,
    )
    amount_due_now = fields.Monetary(
        string='Số tiền đến hạn chưa thu',
        compute='_compute_installment_due_status',
        currency_field='currency_id',
    )
    amount_not_due_yet = fields.Monetary(
        string='Số tiền chưa đến hạn',
        compute='_compute_installment_due_status',
        currency_field='currency_id',
    )

    @api.depends(
        'line_ids.date_maturity',
        'line_ids.amount_residual',
        'line_ids.reconciled',
        'line_ids.account_id.account_type',
        'state',
    )
    def _compute_installment_due_status(self):
        today = fields.Date.context_today(self)
        for move in self:
            if move.state != 'posted' or move.move_type not in ('out_invoice', 'out_refund'):
                move.installment_due_status = 'not_applicable'
                move.amount_due_now = 0.0
                move.amount_not_due_yet = 0.0
                continue

            receivable_lines = move.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
            )
            if not receivable_lines:
                move.installment_due_status = 'not_applicable'
                move.amount_due_now = 0.0
                move.amount_not_due_yet = 0.0
                continue

            unpaid_lines = receivable_lines.filtered(
                lambda l: not l.reconciled and abs(l.amount_residual) > 0.005
            )
            if not unpaid_lines:
                move.installment_due_status = 'paid'
                move.amount_due_now = 0.0
                move.amount_not_due_yet = 0.0
                continue

            due_lines = unpaid_lines.filtered(
                lambda l: l.date_maturity and l.date_maturity <= today
            )
            not_due_lines = unpaid_lines - due_lines

            move.amount_due_now = sum(abs(l.amount_residual) for l in due_lines)
            move.amount_not_due_yet = sum(abs(l.amount_residual) for l in not_due_lines)

            if not due_lines:
                move.installment_due_status = 'not_due'
            elif due_lines and not_due_lines:
                move.installment_due_status = 'partially_due'
            else:
                move.installment_due_status = 'fully_due'