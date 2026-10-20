from odoo import models

# Bảng map tiểu khoản hạch toán (tke_co) theo mã tài khoản bên Có.
# Hard-code theo mô tả template; thêm tài khoản mới thì bổ sung ở đây.
TKE_CO_MAP = {
    "51131": "99010101",
    "13888": "99010102",
}
# Mã đơn vị/account_id của công ty — mặc định theo mô tả template.
DVI_DEFAULT = "9909"

TRICHYEU_PHRASE = "hạch toán doanh thu cước vận chuyển và phụ phí"
TRICHYEU_PHRASE_REFUND = "điều chỉnh giảm doanh thu cước vận chuyển và phụ phí"

# 18 cột đúng thứ tự header sheet "file mau".
HEADERS = [
    "stt", "l_ct", "ngay_ct", "trichyeu",
    "matk_no", "tke_no", "ma_dtu_no", "ma_sp_no", "tien_no", "dvi_sl_no", "note_no",
    "matk_co", "tke_co", "ma_dtu_co", "ma_sp_co", "tien_co", "dvi_sl_co", "note_co",
]
# Index cột tiền để ghi dạng số.
COL_TIEN_NO = 8
COL_TIEN_CO = 15


class HoachToanXlsx(models.AbstractModel):
    _name = "report.account_invoice_hoach_toan.hoach_toan_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Báo cáo xuất hạch toán (XLSX)"

    def generate_xlsx_report(self, workbook, data, objs):
        sheet = workbook.add_worksheet("file mau")
        bold = workbook.add_format({"bold": True})
        money = workbook.add_format({"num_format": "#,##0"})

        for col, name in enumerate(HEADERS):
            sheet.write(0, col, name, bold)

        moves = objs.filtered(
            lambda m: m.move_type in ("out_invoice", "out_refund")
            and m.state == "posted"
        )

        row = 1
        stt = 0
        for move in moves:
            stt += 1

            # --- Bên Nợ: dòng phải thu (payment_term) ---
            recv_lines = move.line_ids.filtered(
                lambda l: l.account_id.account_type
                in ("asset_receivable", "liability_payable")
            )
            matk_no = recv_lines[:1].account_id.code or ""
            # balance (đồng công ty): hóa đơn -> dương, credit note -> âm.
            tien_no = sum(recv_lines.mapped("balance"))

            # --- Bên Có: các dòng còn lại, sản phẩm trước rồi thuế ---
            other_lines = move.line_ids - recv_lines
            product_lines = other_lines.filtered(
                lambda l: not l.tax_line_id and l.account_id
            )
            tax_lines = other_lines.filtered(lambda l: l.tax_line_id)
            credit_lines = product_lines + tax_lines

            dept = move.department_id.name or ""
            partner = move.partner_id.name or ""
            phrase = (
                TRICHYEU_PHRASE_REFUND
                if move.move_type == "out_refund"
                else TRICHYEU_PHRASE
            )
            period = ""
            ngay_ct = ""
            if move.invoice_date:
                period = " T%02d/%04d" % (
                    move.invoice_date.month, move.invoice_date.year
                )
                ngay_ct = move.invoice_date.strftime("%d/%m/%Y")
            # Phần "HĐ {số}" tạm để trống (chưa chốt field nguồn số HĐ).
            prefix = ("%s:" % dept) if dept else ""
            trichyeu = "%s%s %s%s" % (prefix, partner, phrase, period)

            # Gộp bên Có theo (TÀI KHOẢN, external_product_code) — không tách dòng
            # như hóa đơn. Cùng tài khoản nhưng khác mã SP -> mỗi mã 1 dòng; các
            # dòng cùng (tài khoản, mã) được cộng dồn. Giữ thứ tự xuất hiện (sản
            # phẩm trước, thuế sau).
            ccy = move.company_id.currency_id
            groups = {}
            seq = 0
            for line in credit_lines:
                acc = line.account_id
                ext = line.product_id.external_product_code or ""
                key = (acc.id, ext)
                grp = groups.get(key)
                if grp is None:
                    seq += 1
                    grp = groups[key] = {
                        "code": acc.code or "",
                        "ext": ext,
                        "seq": seq,
                        "amount": 0.0,
                    }
                # -balance: doanh thu/thuế bên Có -> dương với HĐ, âm với credit note.
                grp["amount"] += -line.balance

            first = True
            for grp in sorted(groups.values(), key=lambda g: g["seq"]):
                matk_co = grp["code"]
                tke_co = TKE_CO_MAP.get(matk_co, "")
                ma_sp_co = grp["ext"]
                tien_co = ccy.round(grp["amount"])

                values = [
                    stt, "DT", ngay_ct, trichyeu,
                    (matk_no if first else ""), "", "", "",
                    (ccy.round(tien_no) if first else ""), DVI_DEFAULT, "",
                    matk_co, tke_co, "", ma_sp_co, tien_co, DVI_DEFAULT, "",
                ]
                for col, val in enumerate(values):
                    if col in (COL_TIEN_NO, COL_TIEN_CO) and val != "":
                        sheet.write_number(row, col, val, money)
                    else:
                        sheet.write(row, col, val)
                row += 1
                first = False
