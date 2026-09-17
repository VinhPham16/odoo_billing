from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Related + store: để báo cáo doanh thu (pivot/group by trên Journal
    # Items, Sổ cái, các report dựa trên account.move.line) lọc và nhóm được
    # theo phòng ban mà không phải join ngược về account.move.
    # Đọc từ move nên luôn đồng bộ khi đổi phòng ban trên hóa đơn.
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
        related="move_id.department_id",
        store=True,
        index="btree_not_null",
    )
