from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    # Cờ chỉ phục vụ badge ngoài danh sách + filter; KHÔNG hiển thị trên form.
    # copy=False để nút Duplicate không mang cờ sang bản sao.
    hoach_toan_exported = fields.Boolean(
        string="Đã hạch toán", copy=False, readonly=True,
        help="Hóa đơn đã được xuất ra báo cáo hạch toán (nạp phần mềm kế toán ngoài).",
    )
    hoach_toan_export_date = fields.Datetime(
        string="Ngày xuất hạch toán gần nhất", copy=False, readonly=True,
    )
    hoach_toan_export_count = fields.Integer(
        string="Số lần xuất hạch toán", copy=False, readonly=True, default=0,
    )
    # Char thay vì hiển thị trực tiếp boolean: để dùng widget="badge" trên list.
    hoach_toan_badge = fields.Char(
        string="Hạch toán", compute="_compute_hoach_toan_badge",
    )

    @api.depends("hoach_toan_exported")
    def _compute_hoach_toan_badge(self):
        for move in self:
            move.hoach_toan_badge = _("Đã hạch toán") if move.hoach_toan_exported else ""

    def action_mark_hoach_toan_exported(self, period_label=""):
        """Đánh dấu + ghi log chatter cho các chứng từ bán đã vào sổ.

        Gọi từ wizard xuất hạch toán — điểm chốt duy nhất đặt cờ. Lọc lại
        move_type/state ở đây để an toàn kể cả khi được gọi trực tiếp.
        """
        targets = self.filtered(
            lambda m: m.move_type in ("out_invoice", "out_refund")
            and m.state == "posted"
        )
        now = fields.Datetime.now()
        for move in targets:
            count = move.hoach_toan_export_count + 1
            move.write({
                "hoach_toan_exported": True,
                "hoach_toan_export_date": now,
                "hoach_toan_export_count": count,
            })
            if period_label:
                body = _(
                    "Đã xuất báo cáo hạch toán (lần %(n)s) — kỳ %(period)s.",
                    n=count, period=period_label,
                )
            else:
                body = _("Đã xuất báo cáo hạch toán (lần %(n)s).", n=count)
            move.message_post(body=body)
        return targets
