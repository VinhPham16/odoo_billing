from odoo import fields, models, _
from odoo.exceptions import UserError

from .amount_to_words import amount_to_words_vnd

# customer_type (xem module partner_customer_code): '1' Trong nước, '2' Nước ngoài,
# '3' Nội bộ. Khách Nước ngoài và Nội bộ KHÔNG in MST trên hóa đơn
# (nước ngoài không có MST VN; nội bộ theo yêu cầu nghiệp vụ).
CUSTOMER_TYPE_FOREIGN = '2'
CUSTOMER_TYPE_INTERNAL = '3'
CUSTOMER_TYPES_NO_VAT = (CUSTOMER_TYPE_FOREIGN, CUSTOMER_TYPE_INTERNAL)

# Các mức thuế suất GTGT có dòng tổng riêng trên hóa đơn.
VAT_BUCKETS = (0, 5, 8, 10)


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

        # 1) Render PDF bằng template VNPost tùy biến của module này
        #    (KHÔNG dùng report core Odoo).
        pdf_content, _dummy = self.env["ir.actions.report"]._render_qweb_pdf(
            "account_send_draft_invoice.action_report_draft_invoice", self.ids
        )

        # 2) Tạo attachment với tên: YYYYMMDD_{customer name}_{id}.pdf
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

    # ------------------------------------------------------------------
    # Helpers cho template hóa đơn draft (report_draft_invoice)
    # ------------------------------------------------------------------
    def _draft_show_partner_vat(self):
        """True nếu được phép in MST người mua.
        Khách Nước ngoài (type 2) và Nội bộ (type 3): KHÔNG in MST."""
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id or self.partner_id
        if partner.customer_type in CUSTOMER_TYPES_NO_VAT:
            return False
        return bool(partner.vat)

    def _draft_to_company(self, amount):
        """Quy đổi số tiền từ tiền tệ chứng từ sang tiền tệ công ty (VND).

        Hóa đơn phải in theo tiền công ty, KHÔNG dùng nguyên tệ. Dùng đúng tỷ
        giá của chứng từ (theo ngày hóa đơn) và làm tròn theo VND.
        """
        self.ensure_one()
        company = self.company_id
        comp_cur = company.currency_id
        doc_cur = self.currency_id or comp_cur
        if not amount:
            return 0.0
        if doc_cur == comp_cur:
            return comp_cur.round(amount)
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        return doc_cur._convert(amount, comp_cur, company, date)

    @staticmethod
    def _draft_fmt_vnd(amount, blank_zero=False):
        """Định dạng VND: nhóm nghìn bằng '.', không phần thập phân.

        blank_zero=True -> trả '' khi bằng 0 (cột Chiết khấu, ô tổng trống).
        """
        if amount is None:
            return ''
        n = int(round(amount))
        if n == 0 and blank_zero:
            return ''
        return '{:,}'.format(n).replace(',', '.')

    @staticmethod
    def _draft_line_vat_rate(line):
        """Thuế suất GTGT của dòng (tổng các thuế percent). None nếu không có."""
        percents = [t.amount for t in line.tax_ids if t.amount_type == 'percent']
        if not percents:
            return None
        return sum(percents)

    def _draft_line_amounts(self, line):
        """Số tiền của một dòng, ĐÃ quy đổi sang tiền công ty (VND)."""
        self.ensure_one()
        base = self._draft_to_company(line.price_subtotal)
        total = self._draft_to_company(line.price_total)
        gross = self._draft_to_company(line.quantity * line.price_unit)
        return {
            'unit': self._draft_to_company(line.price_unit),
            'discount': gross - base,
            'base': base,
            'tax': total - base,
            'total': total,
        }

    def _draft_product_lines(self):
        """Các dòng hiển thị trên bảng, theo đúng thứ tự trên form."""
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda l: l.display_type in ('product', 'line_note', 'line_section')
        )

    def _draft_tax_summary(self):
        """Gom tiền (VND) theo mức thuế suất để in khối tổng."""
        self.ensure_one()
        summary = {rate: {'base': 0.0, 'tax': 0.0} for rate in VAT_BUCKETS}
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            rate = self._draft_line_vat_rate(line)
            if rate is None:
                continue
            rate_key = int(round(rate))
            if rate_key not in summary:
                continue
            amounts = self._draft_line_amounts(line)
            summary[rate_key]['base'] += amounts['base']
            summary[rate_key]['tax'] += amounts['tax']
        return summary

    def _draft_totals(self):
        """Tổng (VND) cộng dồn từ các dòng đã quy đổi (để Cộng = tổng các dòng)."""
        self.ensure_one()
        totals = {'untaxed': 0.0, 'tax': 0.0, 'total': 0.0}
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
            amounts = self._draft_line_amounts(line)
            totals['untaxed'] += amounts['base']
            totals['tax'] += amounts['tax']
            totals['total'] += amounts['total']
        return totals

    def _draft_amount_in_words(self):
        self.ensure_one()
        return amount_to_words_vnd(self._draft_totals()['total'])
