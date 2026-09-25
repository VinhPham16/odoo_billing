from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # Trục ghi nhận doanh thu là hr.employee chứ không phải res.users:
    # hệ thống có 344 nhân viên nhưng gần như không ai có tài khoản đăng
    # nhập, nên suy phòng ban qua res.users sẽ luôn trả rỗng. Thêm nhân
    # viên kinh doanh mới là việc HR vốn đã làm, không phải tạo thêm tài
    # khoản Odoo.
    #
    # Field thường (không compute) nên không kéo theo dây chuyền tính toán
    # nào lúc save. Cố ý KHÔNG đặt default: kế toán lập hóa đơn cho nhiều
    # nhân viên khác nhau, mặc định theo người đang đăng nhập vừa sai
    # nghiệp vụ vừa tốn thêm một câu search mỗi lần tạo.
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Nhân viên kinh doanh",
        index="btree_not_null",
        tracking=True,
        help="Nhân viên được ghi nhận doanh thu của hóa đơn này. Khác với "
             "Salesperson - Salesperson là người phụ trách hóa đơn trong hệ "
             "thống (thường là kế toán lập hóa đơn).",
    )

    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
        compute="_compute_department_id",
        store=True,
        readonly=False,
        precompute=True,
        tracking=True,
        index="btree_not_null",
        copy=True,
        help="Phòng ban được ghi nhận doanh thu của hóa đơn này. Mặc định "
             "lấy theo phòng ban của Nhân viên kinh doanh, có thể chọn lại "
             "phòng ban khác khi doanh thu thuộc về bộ phận khác.",
    )

    @api.depends("employee_id")
    def _compute_department_id(self):
        """Tự điền phòng ban theo nhân viên kinh doanh, nhưng vẫn cho sửa.

        Pattern "stored compute + readonly=False" của Odoo: tính lại mỗi khi
        đổi nhân viên, ngoài ra người dùng sửa tay thì giữ nguyên giá trị
        sửa tay.

        Chỉ depends duy nhất trên employee_id. KHÔNG khai báo company_id làm
        dependency dù có dùng tới nó về mặt nghiệp vụ: company_id của
        account.move bản thân nó là stored compute có precompute, được tính
        lại trong mỗi lần create/save, nên khai báo phụ thuộc sẽ khiến field
        này bị đánh dấu recompute ở mọi lần save kể cả khi không có gì đổi.

        Đọc employee_id.department_id là một phép đọc quan hệ, ORM prefetch
        theo lô cho cả recordset - không có câu search nào trên đường save.
        Với người dùng không thuộc hr.group_hr_user (kế toán viên), Odoo 19
        tự rơi về hr.employee.public trong fetch(), và department_id nằm
        trong tập field công khai nên đọc được bình thường.
        """
        for move in self:
            if move.employee_id:
                move.department_id = move.employee_id.department_id
            else:
                # Compute bắt buộc gán giá trị cho mọi record trong self.
                # Gán lại chính nó để không xóa lựa chọn thủ công khi bỏ
                # trống nhân viên, và để hóa đơn không phải bán hàng vẫn
                # nhập tay phòng ban được.
                move.department_id = move.department_id
