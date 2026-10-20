from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Cấu hình trước nhân viên kinh doanh cho khách hàng: lập hóa đơn chọn
    # khách hàng là account.move.employee_id tự điền (xem _compute_employee_id
    # ở account_move.py). Trỏ hr.employee cho đồng bộ với field trên hóa đơn -
    # trục ghi nhận doanh thu là nhân viên chứ không phải res.users.
    sale_employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Nhân viên kinh doanh",
        index="btree_not_null",
        help="Nhân viên kinh doanh mặc định của khách hàng này; tự điền lên "
             "hóa đơn khi chọn khách hàng.",
    )

    # Chỉ để HIỂN THỊ trung tâm sẽ áp dụng, không phải điểm cấu hình riêng:
    # related readonly, không store nên không nằm trên đường ghi và không gây
    # nhầm "đặt trung tâm khác nhân viên ở khách hàng". Trên hóa đơn, trung tâm
    # luôn suy từ nhân viên (rule của account.move.department_id không đổi).
    sale_department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Trung tâm kinh doanh",
        related="sale_employee_id.department_id",
        readonly=True,
        help="Trung tâm kinh doanh của Nhân viên kinh doanh; hóa đơn sẽ lấy "
             "trung tâm này qua nhân viên.",
    )
