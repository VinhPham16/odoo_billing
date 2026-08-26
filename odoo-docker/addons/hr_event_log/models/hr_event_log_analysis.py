from odoo import fields, models, tools


class HrEventLogMonthlyReport(models.Model):
    """One row per (month, event_type) with a trailing-3-month average and a
    simple anomaly flag (this month's count > 2x the trailing average).

    This is a heuristic, not statistical anomaly detection - it flags simple
    spikes (e.g. a sudden mass-transfer or clustered leave events) relative
    to recent history. It will not catch gradual drift or subtle patterns.
    """
    _name = "hr.event.log.monthly.report"
    _description = "HR Event Frequency by Month (with anomaly flag)"
    _auto = False
    _order = "month_start desc"

    month_start = fields.Date(string="Month", readonly=True)
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
        string="Event Type", readonly=True,
    )
    event_count = fields.Integer(string="Event Count", readonly=True)
    trailing_avg_3mo = fields.Float(string="Trailing 3-Month Avg", readonly=True)
    is_anomaly = fields.Boolean(string="Anomaly", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH monthly AS (
                    SELECT date_trunc('month', effective_date)::date AS month_start,
                           event_type,
                           count(*) AS event_count
                    FROM hr_event_log
                    GROUP BY 1, 2
                ),
                with_avg AS (
                    SELECT *,
                           AVG(event_count) OVER (
                               PARTITION BY event_type ORDER BY month_start
                               ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                           ) AS trailing_avg_3mo
                    FROM monthly
                )
                SELECT row_number() OVER () AS id,
                       month_start,
                       event_type,
                       event_count,
                       ROUND(COALESCE(trailing_avg_3mo, 0)::numeric, 2) AS trailing_avg_3mo,
                       CASE WHEN trailing_avg_3mo IS NOT NULL AND trailing_avg_3mo > 0
                                 AND event_count > 2 * trailing_avg_3mo
                            THEN true ELSE false END AS is_anomaly
                FROM with_avg
            )
        """ % self._table)


class HrEventLogTurnoverReport(models.Model):
    """One row per month: resignation count, headcount at month end
    (approximated as "employees whose latest event as of that month-end is
    not a resignation" - this does NOT exclude employees on leave at that
    time, since most standard turnover-rate definitions count on-leave staff
    as still part of headcount), and the resulting turnover rate.
    """
    _name = "hr.event.log.turnover.report"
    _description = "HR Turnover Rate by Month"
    _auto = False
    _order = "month_start desc"

    month_start = fields.Date(string="Month", readonly=True)
    resignation_count = fields.Integer(string="Resignations", readonly=True)
    headcount_eom = fields.Integer(string="Headcount (Month End)", readonly=True)
    turnover_rate = fields.Float(string="Turnover Rate (%)", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH bounds AS (
                    SELECT date_trunc('month', MIN(effective_date))::date AS min_month
                    FROM hr_event_log
                ),
                months AS (
                    SELECT generate_series(
                        COALESCE((SELECT min_month FROM bounds), date_trunc('month', CURRENT_DATE)::date),
                        date_trunc('month', CURRENT_DATE)::date,
                        interval '1 month'
                    )::date AS month_start
                ),
                month_ends AS (
                    SELECT month_start,
                           (month_start + interval '1 month - 1 day')::date AS month_end
                    FROM months
                ),
                headcount AS (
                    SELECT me.month_start, count(DISTINCT latest.employee_id) AS headcount
                    FROM month_ends me
                    JOIN LATERAL (
                        SELECT DISTINCT ON (hel.employee_id) hel.employee_id, hel.event_type
                        FROM hr_event_log hel
                        WHERE hel.employee_id IS NOT NULL AND hel.effective_date <= me.month_end
                        ORDER BY hel.employee_id, hel.effective_date DESC, hel.id DESC
                    ) latest ON true
                    WHERE latest.event_type != 'resignation'
                    GROUP BY me.month_start
                ),
                resignations AS (
                    SELECT date_trunc('month', effective_date)::date AS month_start,
                           count(*) AS resignation_count
                    FROM hr_event_log
                    WHERE event_type = 'resignation'
                    GROUP BY 1
                )
                SELECT row_number() OVER () AS id,
                       m.month_start,
                       COALESCE(r.resignation_count, 0) AS resignation_count,
                       COALESCE(h.headcount, 0) AS headcount_eom,
                       CASE WHEN COALESCE(h.headcount, 0) = 0 THEN 0
                            ELSE ROUND(COALESCE(r.resignation_count, 0)::numeric / h.headcount * 100, 2)
                       END AS turnover_rate
                FROM months m
                LEFT JOIN headcount h ON h.month_start = m.month_start
                LEFT JOIN resignations r ON r.month_start = m.month_start
            )
        """ % self._table)


class HrEventLogReconciliationReport(models.Model):
    """Flags employees whose hr.employee.active flag disagrees with what the
    event log says should be true - e.g. still marked Active in Odoo despite
    a logged resignation, or archived with no resignation ever logged. This
    is the 'Status Reconciliation' check for the Audit & Compliance dashboard.
    """
    _name = "hr.event.log.reconciliation.report"
    _description = "HR Status Reconciliation (data integrity check)"
    _auto = False
    _order = "employee_id"

    employee_id = fields.Many2one("hr.employee", string="Employee", readonly=True)
    employee_active_flag = fields.Boolean(string="Marked Active in Odoo", readonly=True)
    latest_event_type = fields.Selection(
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
        string="Latest Logged Event", readonly=True,
    )
    latest_event_date = fields.Date(string="Latest Event Date", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT row_number() OVER () AS id,
                       e.id AS employee_id,
                       e.active AS employee_active_flag,
                       latest.event_type AS latest_event_type,
                       latest.effective_date AS latest_event_date
                FROM hr_employee e
                LEFT JOIN LATERAL (
                    SELECT DISTINCT ON (employee_id) event_type, effective_date
                    FROM hr_event_log
                    WHERE employee_id = e.id
                    ORDER BY employee_id, effective_date DESC, id DESC
                ) latest ON true
                WHERE
                    (e.active = true AND latest.event_type = 'resignation')
                    OR (e.active = false AND (latest.event_type IS DISTINCT FROM 'resignation'))
            )
        """ % self._table)
