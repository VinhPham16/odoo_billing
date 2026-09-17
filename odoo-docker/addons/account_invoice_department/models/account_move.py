from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
        compute="_compute_department_id",
        store=True,
        readonly=False,
        tracking=True,
        index="btree_not_null",
        check_company=True,
        copy=True,
        help="Phòng ban được ghi nhận doanh thu của hóa đơn này. "
             "Mặc định lấy theo phòng ban của Salesperson, có thể chọn lại "
             "phòng ban khác khi doanh thu thuộc về bộ phận khác.",
    )

    @api.depends("invoice_user_id", "company_id")
    def _compute_department_id(self):
        """Tự điền phòng ban theo salesperson, nhưng vẫn cho sửa tay.

        Đây là pattern "stored compute + readonly=False" của Odoo: giá trị
        được tính lại mỗi khi đổi Salesperson (hoặc đổi công ty), ngoài ra
        người dùng sửa tay thì giá trị sửa tay được giữ nguyên.

        Hệ quả cần biết: nếu đã chọn tay một phòng ban rồi mới đổi
        Salesperson thì phòng ban sẽ bị ghi đè theo salesperson mới - đổi
        salesperson được coi là tín hiệu rõ ràng để tính lại. Ngược lại,
        xóa trắng Salesperson KHÔNG xóa phòng ban (nhánh else giữ nguyên
        giá trị cũ), để hóa đơn vẫn ghi nhận được doanh thu phòng ban kể cả
        khi không gắn người bán cụ thể.
        """
        for move in self:
            if move.is_sale_document(include_receipts=True) and move.invoice_user_id:
                move.department_id = move.invoice_user_id._get_hr_department(
                    move.company_id
                )
            else:
                # Compute field bắt buộc gán giá trị cho mọi record trong
                # self, nên gán lại chính nó để giữ nguyên (kể cả với vendor
                # bill / journal entry: không tự điền, nhưng vẫn cho nhập tay).
                move.department_id = move.department_id
