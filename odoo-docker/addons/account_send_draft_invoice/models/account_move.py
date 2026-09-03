from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_send_draft_invoice(self):
        """Gửi hóa đơn bán cho khách khi còn ở trạng thái Draft (proforma).

        Không dùng lại luồng chính thức `account.move.send` vì nó chặn cứng
        các move chưa posted (raise "You can't generate invoices that are not
        posted."). Thay vào đó tự render PDF proforma, đính kèm và mở mail
        composer chuẩn. KHÔNG đánh dấu hóa đơn là 'sent', không sinh số, không
        đổi trạng thái.
        """
        self.ensure_one()

        if self.move_type not in ("out_invoice", "out_refund", "out_receipt"):
            raise UserError(_("Chức năng này chỉ áp dụng cho hóa đơn bán."))

        # 1) Render PDF hóa đơn (bản draft = proforma, có watermark "Draft").
        #    Dùng đúng report mà nút Print đang dùng, chạy tốt trên draft.
        pdf_content, _dummy = self.env["ir.actions.report"]._render_qweb_pdf(
            "account.account_invoices_without_payment", self.ids
        )

        # 2) Tạo attachment với tên: YYYYMMDD_{customer name}_{id}.pdf
        #    - Ngày: invoice_date nếu có, không thì ngày hôm nay.
        #    - Tên khách: làm sạch ký tự đặc biệt (không dùng regex) -> ký tự
        #      không phải chữ/số đổi thành '_', gộp các '_' liên tiếp, bỏ '_' ở 2 đầu.
        #    - Index: self.id (draft chưa có số hóa đơn).
        inv_date = self.invoice_date or fields.Date.context_today(self)
        date_str = inv_date.strftime("%Y%m%d")
        raw_name = self.partner_id.name or "Unknown"
        safe_name = "".join(c if c.isalnum() else "_" for c in raw_name)
        safe_name = "_".join(part for part in safe_name.split("_") if part) or "Unknown"
        filename = "%s_%s_%s.pdf" % (date_str, safe_name, self.id)

        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "raw": pdf_content,
            "mimetype": "application/pdf",
            "res_model": "account.move",
            "res_id": self.id,
        })

        # 3) Nạp template email hóa đơn có sẵn (nếu có).
        template = self.env.ref(
            "account.email_template_edi_invoice", raise_if_not_found=False
        )

        # 4) Mở mail composer với PDF đính kèm sẵn.
        compose_ctx = {
            "default_model": "account.move",
            "default_res_ids": self.ids,
            "default_composition_mode": "comment",
            "default_attachment_ids": [(6, 0, attachment.ids)],
            "default_email_layout_xmlid": "mail.mail_notification_layout_with_responsible_signature",
            "force_email": True,
        }
        if template:
            compose_ctx["default_template_id"] = template.id
            compose_ctx["default_use_template"] = True

        return {
            "name": _("Gửi hóa đơn (Draft)"),
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": compose_ctx,
        }
