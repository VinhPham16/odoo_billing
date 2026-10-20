from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Cấu hình ký hiệu HĐĐT đặt ngay trên sổ nhật ký (không fix cứng trong code,
    # không nằm ở res.company) — cùng triết lý với account_invoice_disbursement.
    # Mỗi dải hóa đơn = một sổ với một mẫu ký hiệu riêng, vd 2 sổ bán chính cấu
    # hình '1K{yy}TAA' và '1K{yy}TAB'.
    ky_hieu_hddt = fields.Char(
        string='Ký hiệu HĐĐT',
        help="Mẫu ký hiệu hóa đơn điện tử cho sổ này (vd '1K{yy}TAA').\n"
             "- {yy}  : 2 chữ số cuối của năm (2026 -> 26)\n"
             "- {yyyy}: năm đầy đủ (2026)\n"
             "Phần năm tự thay theo Ngày hóa đơn của từng chứng từ, nên sang "
             "năm mới không phải sửa tay (2026 -> 1K26TAA, 2027 -> 1K27TAA). "
             "Nếu không có {yy}/{yyyy} thì dùng nguyên văn như chuỗi tĩnh.",
    )
