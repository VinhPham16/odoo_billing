from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Ký hiệu HĐĐT đã resolve của chứng từ. Stored + index để lọc/gom nhóm trên
    # danh sách hóa đơn như partner_id/invoice_date.
    ky_hieu_hddt = fields.Char(
        string='Ký hiệu HĐĐT',
        compute='_compute_ky_hieu_hddt',
        store=True,
        readonly=False,
        precompute=True,
        index='btree_not_null',
        copy=False,
        tracking=True,
        help="Ký hiệu HĐĐT của chứng từ, mặc định suy từ mẫu ký hiệu trên sổ "
             "nhật ký với phần năm thay theo Ngày hóa đơn. Sửa tay được.",
    )

    @api.depends('journal_id', 'invoice_date', 'date')
    def _compute_ky_hieu_hddt(self):
        """Suy ký hiệu HĐĐT từ mẫu trên sổ, tự cuốn năm theo ngày chứng từ.

        Pattern "stored compute + readonly=False + precompute" (giống
        department_id của account_invoice_department): chốt giá trị ngay khi tạo
        và cho sửa tay.

        CỐ Ý chỉ depends trên 'journal_id' (quan hệ) + ngày, KHÔNG depends
        'journal_id.ky_hieu_hddt'. Hệ quả:

        1. Sửa mẫu ký hiệu trên sổ KHÔNG ghi đè ký hiệu đã chốt trên hóa đơn cũ
           (snapshot đóng băng). Phần năm vẫn tự đổi khi Ngày hóa đơn đổi — bản
           chất năm phải bám ngày lập; hóa đơn đã phát hành có ngày cố định nên
           ký hiệu cũng cố định.
        2. KHÔNG backfill dữ liệu cũ: field ky_hieu_hddt trên account.journal
           cũng mới sinh trong chính module này, nên lúc cài (-i) khởi tạo cột
           này trên account.move thì mọi sổ còn rỗng -> hóa đơn cũ nhận rỗng.
           Việc cấu hình mẫu trên sổ diễn ra SAU khi cài, và vì không depends mẫu
           sổ nên hóa đơn cũ không bao giờ bị tính lại.
        """
        for move in self:
            template = move.journal_id.ky_hieu_hddt
            if template:
                d = move.invoice_date or move.date or fields.Date.context_today(move)
                move.ky_hieu_hddt = self._format_ky_hieu_hddt(template, d)
            else:
                # Sổ chưa cấu hình: giữ nguyên giá trị (kể cả nhập tay). Compute
                # vẫn phải gán cho mọi record trong self.
                move.ky_hieu_hddt = move.ky_hieu_hddt

    @staticmethod
    def _format_ky_hieu_hddt(template, date):
        """Thay token năm trong mẫu ký hiệu bằng năm của ngày chứng từ."""
        return (
            template
            .replace('{yyyy}', date.strftime('%Y'))
            .replace('{yy}', date.strftime('%y'))
        )
