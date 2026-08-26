from odoo import fields, models


class HrEventLogMapping(models.Model):
    """One configurable master-data list, mirroring the original Excel
    'Mapping' sheet: a single table where HR/IT can add/edit lookup values
    without touching code, grouped by category.

    Only used for lookups Odoo has NO native model for. Department, Job
    Position, and Work Location are Odoo-native (hr.department, hr.job,
    hr.work.location) and are reused directly on hr.event.log - they are
    NOT duplicated here.
    """
    _name = "hr.event.log.mapping"
    _description = "HR Event Log Master Data"
    _order = "category, sequence, name"

    name = fields.Char(string="Value", required=True)
    category = fields.Selection(
        [
            ("classification", "Labor Classification (EBIT)"),
            ("job_title_group", "Job Title Group"),
            ("contract_type", "Contract Type"),
            ("salary_scale", "Salary Scale"),
            ("salary_scale_group", "Salary Scale Group"),
            ("salary_grade", "Salary Grade"),
        ],
        string="Category", required=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "name_category_uniq",
            "unique(name, category)",
            "This value already exists in this category.",
        ),
    ]
