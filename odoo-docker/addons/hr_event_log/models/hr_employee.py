from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # ---- fields with no native Odoo equivalent, mirroring hr.event.log's
    # own custom fields 1:1 so event data can be written back onto the live
    # employee record, not just kept in the log. Prefixed event_log_* to
    # avoid clashing with any current or future native hr.employee field
    # (e.g. the native contract_type_id already exists and points to a
    # different model, hr.contract.type, not hr.event.log.mapping). ----
    event_log_classification_id = fields.Many2one(
        "hr.event.log.mapping", string="Labor Classification (EBIT)",
        domain=[("category", "=", "classification")],
    )
    event_log_job_title_group_id = fields.Many2one(
        "hr.event.log.mapping", string="Job Title Group",
        domain=[("category", "=", "job_title_group")],
    )
    event_log_contract_type_id = fields.Many2one(
        "hr.event.log.mapping", string="Contract Type (Event Log)",
        domain=[("category", "=", "contract_type")],
    )
    event_log_salary_scale_id = fields.Many2one(
        "hr.event.log.mapping", string="Salary Scale",
        domain=[("category", "=", "salary_scale")],
    )
    event_log_salary_scale_group_id = fields.Many2one(
        "hr.event.log.mapping", string="Salary Scale Group",
        domain=[("category", "=", "salary_scale_group")],
    )
    event_log_salary_grade_id = fields.Many2one(
        "hr.event.log.mapping", string="Salary Grade",
        domain=[("category", "=", "salary_grade")],
    )
    event_log_team = fields.Char(string="Team/Group (To/Nhom)")
    event_log_personal_email = fields.Char(string="Personal Email")
    event_log_address = fields.Char(string="Current Address (Event Log)")
    event_log_gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")], string="Gender"
    )
    event_log_education_general = fields.Char(string="General Education Level")
    event_log_education_level = fields.Char(string="Training Level")

    # ---- event-specific fields (resignation/leave/new-hire one-offs) -
    # also mirrored so every hr.event.log field has a home on the employee
    # record, not just the "profile" subset shared across event types. ----
    event_log_job_offer_text = fields.Char(string="Job Offer Position")
    event_log_last_working_day = fields.Date(string="Last Working Day")
    event_log_resignation_reason_type = fields.Selection(
        [("voluntary", "Voluntary"), ("involuntary", "Involuntary")],
        string="Resignation Type",
    )
    event_log_leave_start_date = fields.Date(string="Leave Start Date")
    event_log_leave_expected_return_date = fields.Date(string="Expected Return Date")
    event_log_leave_coverage_employee_id = fields.Many2one(
        "hr.employee", string="Temporary Coverage By"
    )
    event_log_leave_paid = fields.Boolean(string="Paid Leave")
    event_log_is_unplanned_leave = fields.Boolean(string="Unplanned Leave")
    event_log_notes = fields.Text(string="Latest Event Notes")

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

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        if not self.env.context.get("skip_event_log_creation"):
            # Any employee created outside the "Log HR Event" New Hire flow
            # (e.g. directly via the Employees app, an import, another
            # module) still needs a baseline New Hire row - otherwise they
            # never show up in Active Roster / New Hire Volume / tenure_days
            # (all built purely from hr.event.log data).
            sync_map = self.env["hr.event.log"].EMPLOYEE_SYNC_FIELD_MAP
            for emp in employees:
                # sudo(): some source fields (e.g. contract_date_start) are
                # restricted to Employees/Administrator - whoever has rights
                # to create the employee must still be able to read their
                # own just-entered values back for the auto-logged event.
                emp_sudo = emp.sudo()
                event_vals = {
                    "employee_id": emp.id,
                    "event_type": "new_hire",
                    "effective_date": fields.Date.context_today(self),
                }
                for log_field, emp_field in sync_map.items():
                    value = emp_sudo[emp_field]
                    if value:
                        event_vals[log_field] = value.id if hasattr(value, "id") else value
                # sudo(): system-triggered side effect of creating an
                # employee, not a direct hr.event.log edit by the user.
                self.env["hr.event.log"].sudo().create(event_vals)
        return employees

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
