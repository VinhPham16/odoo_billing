from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    event_log_ids = fields.One2many(
        "hr.event.log", "employee_id", string="HR Event History"
    )
    event_log_count = fields.Integer(
        string="Event Count", compute="_compute_event_log_count"
    )
    current_hr_status = fields.Selection(
        [
            ("working", "Working"),
            ("on_leave", "On Leave"),
            ("resigned", "Resigned"),
        ],
        string="Current HR Status",
        compute="_compute_current_hr_status",
        # Not stored: this is a read-derived value from the append-only log,
        # recomputing it on every read avoids needing recompute hooks wired
        # into hr.event.log's create() (which is the only way records are
        # ever added, since write/unlink are blocked) - see
        # hr_event_log_reports.py for the same reasoning applied to the
        # Active Roster / Leavers SQL views.
        store=False,
    )

    def _compute_event_log_count(self):
        for emp in self:
            emp.event_log_count = len(emp.event_log_ids)

    def _compute_current_hr_status(self):
        for emp in self:
            latest = self.env["hr.event.log"].search(
                [("employee_id", "=", emp.id)],
                order="effective_date desc, id desc", limit=1,
            )
            if not latest:
                emp.current_hr_status = "working" if emp.active else "resigned"
            elif latest.event_type == "resignation":
                emp.current_hr_status = "resigned"
            elif (
                latest.event_type in ("maternity_leave", "extended_leave")
                and latest.leave_start_date and latest.leave_start_date <= fields.Date.today()
                and (not latest.leave_expected_return_date
                     or latest.leave_expected_return_date >= fields.Date.today())
            ):
                emp.current_hr_status = "on_leave"
            else:
                emp.current_hr_status = "working"

    def action_view_event_log(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "HR Event History",
            "res_model": "hr.event.log",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    def action_log_hr_event(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Log HR Event",
            "res_model": "hr.event.log",
            "view_mode": "form",
            "target": "new",
            "context": {"default_employee_id": self.id},
        }
