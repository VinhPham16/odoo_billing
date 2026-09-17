from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_hr_department(self, company=None):
        """Trả về phòng ban của nhân viên (hr.employee) gắn với user này.

        Dùng sudo() vì hr.employee chỉ cho group_hr_user đọc (xem
        hr/security/ir.model.access.csv), trong khi kế toán viên - người
        nhập hóa đơn - thường không nằm trong nhóm đó. Bản thân
        hr.department thì base.group_user đọc được, nên field phòng ban
        trên hóa đơn vẫn hiển thị bình thường sau khi đã điền.

        Lưu ý Odoo 19: hr.employee _inherits hr.version, department_id nằm
        trên hr.version và được delegate xuống employee - đọc/search qua
        employee.department_id vẫn đúng.

        :param company: res.company để ưu tiên tìm nhân viên cùng công ty
            (một user có thể có nhiều hr.employee ở nhiều công ty).
        :return: recordset hr.department (rỗng nếu không tìm thấy).
        """
        self.ensure_one()
        department_model = self.env["hr.department"]
        if not self.id:
            return department_model.browse()

        employee_model = self.env["hr.employee"].sudo()
        domain = [("user_id", "=", self.id)]
        company = company or self.env.company
        employee = employee_model.search(
            domain + [("company_id", "=", company.id)], limit=1
        )
        if not employee:
            # User chưa có nhân viên ở công ty hiện tại: lấy tạm nhân viên
            # bất kỳ của user đó, nhưng chỉ nhận phòng ban dùng chung
            # (company_id rỗng) để không vi phạm check_company khi ghi.
            employee = employee_model.search(domain, limit=1)
            if employee.department_id.company_id:
                return department_model.browse()

        # browse() lại bằng env của self để không trả về recordset sudo.
        return department_model.browse(employee.department_id.id)
