from odoo import fields, models, tools

# Design choice: "latest row per employee" is a window-function problem
# (PostgreSQL DISTINCT ON), which the database handles far more efficiently
# and correctly than recomputing it in Python on every list refresh via a
# stored computed field. These two _auto=False SQL views are read-only by
# nature and never need to be searched/grouped outside their own list views,
# so there's no benefit to denormalizing them into stored fields.


class HrEventLogActiveReport(models.Model):
    """Active roster: latest event per employee, excluding anyone whose
    latest event is a resignation or a currently-active leave-type event."""
    _name = "hr.event.log.active.report"
    _description = "HR Active Roster (latest event per employee)"
    _auto = False
    _order = "employee_id"

    employee_id = fields.Many2one("hr.employee", string="Employee", readonly=True)
    latest_event_id = fields.Many2one("hr.event.log", string="Latest Event", readonly=True)
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
        string="Latest Event Type", readonly=True,
    )
    effective_date = fields.Date(string="Effective Date", readonly=True)
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
    job_id = fields.Many2one("hr.job", string="Job Position", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    latest.employee_id AS employee_id,
                    latest.id AS latest_event_id,
                    latest.event_type AS event_type,
                    latest.effective_date AS effective_date,
                    latest.department_id AS department_id,
                    latest.job_id AS job_id
                FROM (
                    SELECT DISTINCT ON (employee_id) *
                    FROM hr_event_log
                    WHERE employee_id IS NOT NULL
                    ORDER BY employee_id, effective_date DESC, id DESC
                ) latest
                WHERE latest.event_type != 'resignation'
                  AND NOT (
                        latest.event_type IN ('maternity_leave', 'extended_leave')
                        AND latest.leave_start_date <= CURRENT_DATE
                        AND (latest.leave_expected_return_date IS NULL
                             OR latest.leave_expected_return_date >= CURRENT_DATE)
                  )
            )
        """ % self._table)


class HrEventLogLeaverReport(models.Model):
    """Leavers: employees whose latest event is a resignation, newest first."""
    _name = "hr.event.log.leaver.report"
    _description = "HR Leavers (latest event = resignation)"
    _auto = False
    _order = "effective_date desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", readonly=True)
    latest_event_id = fields.Many2one("hr.event.log", string="Resignation Event", readonly=True)
    effective_date = fields.Date(string="Effective Date", readonly=True)
    last_working_day = fields.Date(string="Last Working Day", readonly=True)
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
    job_id = fields.Many2one("hr.job", string="Job Position", readonly=True)
    notes = fields.Text(string="Notes", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    latest.employee_id AS employee_id,
                    latest.id AS latest_event_id,
                    latest.effective_date AS effective_date,
                    latest.last_working_day AS last_working_day,
                    latest.department_id AS department_id,
                    latest.job_id AS job_id,
                    latest.notes AS notes
                FROM (
                    SELECT DISTINCT ON (employee_id) *
                    FROM hr_event_log
                    WHERE employee_id IS NOT NULL
                    ORDER BY employee_id, effective_date DESC, id DESC
                ) latest
                WHERE latest.event_type = 'resignation'
                ORDER BY latest.effective_date DESC
            )
        """ % self._table)
