from odoo import fields, models, _
from odoo.exceptions import UserError


class HoachToanExportWizard(models.TransientModel):
    _name = "hoach.toan.export.wizard"
    _description = "Xuất báo cáo hạch toán"

    date_from = fields.Date(string="Từ ngày", required=True)
    date_to = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one(
        "res.company", string="Công ty", required=True,
        default=lambda self: self.env.company,
    )
    journal_ids = fields.Many2many(
        "account.journal", string="Sổ nhật ký",
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        help="Để trống = lấy tất cả sổ bán hàng của công ty.",
    )
    exclude_exported = fields.Boolean(
        string="Bỏ qua hóa đơn đã hạch toán", default=True,
        help="Mặc định không xuất lại HĐ đã hạch toán. Bỏ tick để xuất lại.",
    )

    def action_export(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("“Từ ngày” phải nhỏ hơn hoặc bằng “Đến ngày”."))

        domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
        ]
        if self.journal_ids:
            domain.append(("journal_id", "in", self.journal_ids.ids))
        if self.exclude_exported:
            domain.append(("hoach_toan_exported", "=", False))

        moves = self.env["account.move"].search(domain, order="invoice_date, name")
        if not moves:
            raise UserError(_("Không có hóa đơn nào khớp điều kiện để xuất."))

        period_label = "%s–%s" % (
            self.date_from.strftime("%d/%m/%Y"),
            self.date_to.strftime("%d/%m/%Y"),
        )
        # Điểm chốt duy nhất đặt cờ + ghi log.
        moves.action_mark_hoach_toan_exported(period_label=period_label)

        return self.env.ref(
            "account_invoice_hoach_toan.action_hoach_toan_xlsx"
        ).report_action(moves)
