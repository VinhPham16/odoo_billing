from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEventLog(models.Model):
    """Append-only HR event log. One row = one HR event for one employee.

    Ported from an Excel/VBA tool where 'Master Data' was a single
    append-only sheet, and 'Active Data' / 'Leavers' were views rebuilt from
    "the most recent row per employee". Odoo has no native row-lock, so
    append-only is enforced here at the ORM level (write/unlink overrides
    below), not just hidden in the UI.

    Wherever Odoo already has a native model for something (Department, Job
    Position, Work Location), this reuses it via Many2one instead of
    duplicating it as free text or a separate list.
    """
    _name = "hr.event.log"
    _description = "HR Event Log"
    _order = "effective_date desc, id desc"
    _rec_name = "event_ref"

    # Field-visibility mapping per event type - carried over directly from
    # the original VBA tool's RelevantCols() table.
    EVENT_FIELD_MAP = {
        "new_hire": [
            "department_id", "job_id", "work_location_id", "team",
            "job_offer_text", "classification_id", "job_title_group_id",
            "work_phone", "work_email", "personal_email", "address",
            "birthday", "gender", "identification_id",
            "education_general", "education_level",
            "contract_type_id", "contract_date_start", "contract_date_end",
        ],
        "resignation": ["last_working_day", "resignation_reason_type", "notes"],
        "transfer": ["department_id", "job_id", "team", "notes"],
        "promotion": ["job_id", "job_title_group_id", "notes"],
        "salary_contract_change": [
            "contract_type_id", "contract_date_start", "contract_date_end",
            "salary_scale_id", "salary_scale_group_id", "salary_grade_id", "notes",
        ],
        "maternity_leave": ["leave_start_date", "leave_expected_return_date", "leave_coverage_employee_id", "is_unplanned_leave", "notes"],
        "extended_leave": ["leave_start_date", "leave_expected_return_date", "leave_paid", "is_unplanned_leave", "notes"],
        "return_to_work": ["department_id", "job_id", "notes"],
    }

    CORE_FIELDS = ["employee_id", "event_type", "effective_date"]
    LEAVE_EVENT_TYPES = ("maternity_leave", "extended_leave")

    # Profile fields auto-filled from the employee's latest log entry
    # (or their live hr.employee record if no prior entry exists yet).
    PROFILE_FIELDS = [
        "department_id", "job_id", "work_location_id", "team",
        "classification_id", "job_title_group_id",
        "work_phone", "work_email", "personal_email", "address",
        "birthday", "gender", "identification_id",
        "education_general", "education_level",
        "contract_type_id", "contract_date_start", "contract_date_end",
    ]

    event_ref = fields.Char(
        string="Event ID", readonly=True, copy=False,
        help="Auto-generated as <employee ref>-<sequence>, e.g. EMP0123-02.",
    )
    employee_id = fields.Many2one(
        "hr.employee", string="Employee",
        help="Leave blank only when Event type = New Hire (the employee record "
             "itself may not exist yet). Required for every other event type.",
    )
    event_type = fields.Selection(
        [
            ("new_hire", "New Hire"),
            ("transfer", "Transfer"),
            ("promotion", "Promotion"),
            ("salary_contract_change", "Salary / Contract Change"),
            ("maternity_leave", "Maternity Leave"),
            ("extended_leave", "Extended Leave / Unpaid Leave"),
            ("resignation", "Resignation"),
            ("return_to_work", "Return to Work"),
        ],
        string="Event Type", required=True,
    )
    effective_date = fields.Date(string="Effective Date", required=True)

    # ---- reused native Odoo fields (NOT duplicated) ----
    department_id = fields.Many2one("hr.department", string="Department")
    job_id = fields.Many2one("hr.job", string="Job Position (Chuc danh)")
    work_location_id = fields.Many2one("hr.work.location", string="Work Location")

    # ---- fields with no native Odoo equivalent, sourced from configurable
    #      hr.event.log.mapping master data ----
    classification_id = fields.Many2one(
        "hr.event.log.mapping", string="Labor Classification (EBIT)",
        domain=[("category", "=", "classification")],
    )
    job_title_group_id = fields.Many2one(
        "hr.event.log.mapping", string="Job Title Group",
        domain=[("category", "=", "job_title_group")],
    )
    contract_type_id = fields.Many2one(
        "hr.event.log.mapping", string="Contract Type",
        domain=[("category", "=", "contract_type")],
    )
    salary_scale_id = fields.Many2one(
        "hr.event.log.mapping", string="Salary Scale",
        domain=[("category", "=", "salary_scale")],
    )
    salary_scale_group_id = fields.Many2one(
        "hr.event.log.mapping", string="Salary Scale Group",
        domain=[("category", "=", "salary_scale_group")],
    )
    salary_grade_id = fields.Many2one(
        "hr.event.log.mapping", string="Salary Grade",
        domain=[("category", "=", "salary_grade")],
    )

    # ---- plain fields that had no dropdown in the original tool either ----
    team = fields.Char(string="Team/Group (To/Nhom)")
    job_offer_text = fields.Char(string="Job Offer Position")
    work_phone = fields.Char(string="Work Phone")
    work_email = fields.Char(string="Work Email")
    personal_email = fields.Char(string="Personal Email")
    address = fields.Char(string="Current Address")
    birthday = fields.Date(string="Date of Birth")
    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")], string="Gender"
    )
    identification_id = fields.Char(string="ID/CCCD Number")
    education_general = fields.Char(string="General Education Level")
    education_level = fields.Char(string="Training Level")
    contract_date_start = fields.Date(string="Contract From")
    contract_date_end = fields.Date(string="Contract To")

    # ---- event-specific one-off fields (never auto-filled) ----
    last_working_day = fields.Date(string="Last Working Day")
    leave_start_date = fields.Date(string="Leave Start Date")
    leave_expected_return_date = fields.Date(string="Expected Return Date")
    leave_coverage_employee_id = fields.Many2one("hr.employee", string="Temporary Coverage By")
    leave_paid = fields.Boolean(string="Paid Leave")
    notes = fields.Text(string="Notes")

    # ---- added for reporting (not in the original VBA tool - needed to
    # answer "voluntary vs involuntary" and "planned vs unplanned" questions
    # that a pure event-type log can't answer on its own) ----
    resignation_reason_type = fields.Selection(
        [("voluntary", "Voluntary"), ("involuntary", "Involuntary")],
        string="Resignation Type", default="voluntary",
        help="Used for Leaver Analysis reporting (voluntary vs involuntary attrition).",
    )
    is_unplanned_leave = fields.Boolean(
        string="Unplanned",
        help="Tick for sick leave / unscheduled absence. Used for the Absenteeism "
             "Rate report. Leave unticked for planned leave (e.g. approved vacation).",
    )

    # ---- stored computed measures, so native Odoo Graph/Pivot views can
    # group/measure on them directly (non-stored fields can't be used as
    # pivot measures reliably) ----
    leave_days = fields.Integer(
        string="Leave Days", compute="_compute_leave_days", store=True,
        help="leave_expected_return_date - leave_start_date, for leave-type events only.",
    )
    tenure_days = fields.Integer(
        string="Tenure at Event (Days)", compute="_compute_tenure_days", store=True,
        help="Days between this employee's earliest logged New Hire event and this "
             "event's effective date. Falls back to their hr.employee record creation "
             "date if no New Hire event was ever logged for them (e.g. migrated data).",
    )

    active = fields.Boolean(default=True, help="Permanent log entry - never deactivated via UI.")

    @api.depends("leave_start_date", "leave_expected_return_date")
    def _compute_leave_days(self):
        for rec in self:
            if rec.leave_start_date and rec.leave_expected_return_date:
                rec.leave_days = (rec.leave_expected_return_date - rec.leave_start_date).days
            else:
                rec.leave_days = 0

    @api.depends("employee_id", "effective_date")
    def _compute_tenure_days(self):
        for rec in self:
            if not rec.employee_id or not rec.effective_date:
                rec.tenure_days = 0
                continue
            hire_event = self.search([
                ("employee_id", "=", rec.employee_id.id),
                ("event_type", "=", "new_hire"),
            ], order="effective_date asc", limit=1)
            if hire_event:
                hire_date = hire_event.effective_date
            else:
                hire_date = rec.employee_id.create_date.date() if rec.employee_id.create_date else rec.effective_date
            rec.tenure_days = max((rec.effective_date - hire_date).days, 0)

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if "effective_date" in fields_list and not defaults.get("effective_date"):
            defaults["effective_date"] = fields.Date.context_today(self)
        return defaults

    @api.model
    def get_import_templates(self):
        return [{
            "label": _("Import Template for New Hire Onboarding"),
            "template": "/hr_event_log/static/xls/hr_event_log_new_hire_import_template.csv",
        }]

    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.event_ref:
                # sudo(): barcode is a privacy-restricted hr.employee field
                # (HR Officer only), but any user allowed to create event
                # log entries must be able to generate a ref from it.
                emp = rec.employee_id.sudo()
                ref = (emp.barcode or emp.identification_id
                       or (str(rec.employee_id.id) if rec.employee_id else "NEWHIRE"))
                count = self.search_count([
                    ("employee_id", "=", rec.employee_id.id),
                    ("id", "<=", rec.id),
                ]) if rec.employee_id else 1
                # Bypass both the append-only write() guard below and the
                # ir.rule that backs it (sudo()): this is still part of the
                # initial create, not an edit of an existing entry, so it
                # must not require group_event_log_admin.
                models.Model.write(rec.sudo(), {"event_ref": "%s-%02d" % (ref, count)})
        return records

    # -----------------------------------------------------------------
    # Append-only enforcement (ORM-level, so XML-RPC/API callers can't bypass it)
    # -----------------------------------------------------------------
    def write(self, vals):
        if not self.env.user.has_group("hr_event_log.group_event_log_admin"):
            raise UserError(_(
                "HR Event Log entries are append-only. Existing records cannot be "
                "edited. If a correction is needed, add a new event row instead."
            ))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("hr_event_log.group_event_log_admin"):
            raise UserError(_(
                "HR Event Log entries are append-only. Existing records cannot be "
                "deleted. If a correction is needed, add a new event row instead."
            ))
        return super().unlink()

    def toggle_active(self):
        raise UserError(_("HR Event Log entries cannot be archived or deactivated."))

    # -----------------------------------------------------------------
    # Auto-fill: prefer latest hr.event.log row for this employee; fall back
    # to the live hr.employee record only if no prior log entry exists yet.
    # -----------------------------------------------------------------
    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if not self.employee_id or self.event_type == "new_hire":
            return

        latest_log = self.search([
            ("employee_id", "=", self.employee_id.id),
            ("id", "!=", self._origin.id if self._origin else False),
        ], order="effective_date desc, id desc", limit=1)

        if latest_log:
            for f in self.PROFILE_FIELDS:
                setattr(self, f, latest_log[f])
            return

        emp = self.employee_id
        self.department_id = emp.department_id
        self.job_id = emp.job_id
        self.work_location_id = emp.work_location_id
        self.work_phone = emp.work_phone
        self.work_email = emp.work_email
        self.birthday = emp.birthday
        self.gender = emp.gender
        self.identification_id = emp.identification_id
        contract = emp.contract_id if "contract_id" in emp._fields else False
        if contract:
            self.contract_date_start = contract.date_start
            self.contract_date_end = contract.date_end
