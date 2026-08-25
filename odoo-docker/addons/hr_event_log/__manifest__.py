{
    "name": "HR Event Log",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Append-only HR event log built into the Employees app (new hire, transfer, promotion, leave, resignation, return)",
    "description": """
HR Event Log
============
Ports an existing Excel/VBA HR event-tracking tool into native Odoo, built
directly into the Employees app rather than as a separate top-level app.

- hr.event.log: append-only log of HR events per employee.
- Lives on the employee form as a smart button + history tab, and as a
  "Log HR Event" action - no separate module UI to learn.
- Dynamic form: selecting an event type shows only the fields relevant to it.
- Selecting an employee auto-fills their profile fields from their latest
  event log entry (falls back to their live hr.employee record if they have
  no prior log entry yet).
- hr.employee gains a computed, non-stored "Current HR Status" field
  (Working / On Leave / Resigned) driven by the event log.
- Active Roster and Leavers are read-only SQL-view reports under
  Employees > Reporting.
- hr.event.log.mapping: one configurable master-data list (mirrors the
  original Excel "Mapping" sheet) for the lookup lists Odoo has no native
  model for - Labor Classification, Job Title Group, Contract Type,
  Salary Scale, Salary Scale Group, Salary Grade. Everything Odoo already
  has natively (Department, Job Position, Work Location) is reused as-is,
  not duplicated.
- Append-only enforcement at the ORM level (write/unlink blocked for
  non-admins) plus a record rule as defense in depth against direct RPC.
""",
    "author": "VNPL IT/Digital",
    "depends": ["hr"],
    "data": [
        "security/hr_event_log_security.xml",
        "security/ir.model.access.csv",
        "views/hr_event_log_mapping_views.xml",
        "views/hr_event_log_views.xml",
        "views/hr_event_log_analytics_views.xml",
        "views/hr_event_log_report_views.xml",
        "views/hr_event_log_dashboard_views.xml",
        "views/hr_event_log_dashboard_actions.xml",
        "views/hr_employee_views.xml",
        "views/hr_event_log_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
