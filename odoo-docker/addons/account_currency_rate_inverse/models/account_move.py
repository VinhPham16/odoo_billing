from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_currency_rate_inverse = fields.Float(
        string="Currency Rate (inverse)",
        compute="_compute_invoice_currency_rate_inverse",
        inverse="_inverse_invoice_currency_rate_inverse",
        digits=0,
        help="Tỷ giá đọc theo chiều quen thuộc: bao nhiêu đơn vị tiền tệ công "
             "ty cho 1 đơn vị tiền tệ hóa đơn (ví dụ 25.820 VND = 1 USD). "
             "Đây là nghịch đảo của Currency Rate, hai ô luôn khớp nhau.",
    )

    # digits=0 ở tầng Python nghĩa là giữ nguyên độ chính xác float, không làm
    # tròn - giống cách core khai báo res.currency.rate.inverse_company_rate.
    # Việc làm tròn chỉ xảy ra ở tầng hiển thị (thuộc tính digits trong view).

    @api.depends("invoice_currency_rate")
    def _compute_invoice_currency_rate_inverse(self):
        for move in self:
            rate = move.invoice_currency_rate
            move.invoice_currency_rate_inverse = (1.0 / rate) if rate else 0.0

    @api.onchange("invoice_currency_rate_inverse")
    def _inverse_invoice_currency_rate_inverse(self):
        """Ghi ngược về invoice_currency_rate khi người dùng nhập chiều nghịch.

        Vừa khai báo `inverse=` (để write/RPC hoạt động) vừa decorate
        @api.onchange (để form cập nhật tức thì) - đúng cặp mà core dùng cho
        res.currency.rate._inverse_inverse_company_rate.
        """
        for move in self:
            inverse = move.invoice_currency_rate_inverse
            if inverse:
                move.invoice_currency_rate = 1.0 / inverse

    def _sanitize_rate_vals(self, vals):
        """Chiều thuận thắng khi cả hai chiều cùng có trong vals.

        Khi người dùng gõ ô nghịch đảo, @api.onchange đã cập nhật luôn
        invoice_currency_rate, nên web client gửi CẢ HAI field lúc save. Giữ
        chiều thuận là đúng ở cả hai hướng chỉnh sửa, vì giá trị đó luôn được
        tính từ ô người dùng gõ với độ chính xác float đầy đủ - trong khi ô
        nghịch đảo chỉ mang giá trị đã làm tròn theo digits của view.

        Mượn nguyên cách core xử lý ở res.currency.rate._sanitize_vals.
        """
        if "invoice_currency_rate" in vals and "invoice_currency_rate_inverse" in vals:
            vals = dict(vals)
            del vals["invoice_currency_rate_inverse"]
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._sanitize_rate_vals(vals) for vals in vals_list])

    def write(self, vals):
        return super().write(self._sanitize_rate_vals(vals))
