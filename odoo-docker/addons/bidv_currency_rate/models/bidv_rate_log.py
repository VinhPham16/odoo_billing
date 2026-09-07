from odoo import fields, models


class BidvExchangeRateLog(models.Model):
    _name = "bidv.exchange.rate.log"
    _description = "BIDV Exchange Rate Fetch Log"
    _order = "create_date desc"

    date = fields.Date(string="Business Date", index=True)
    provider_day = fields.Char(string="BIDV Day")
    provider_hour = fields.Char(string="BIDV Hour")
    namerecord = fields.Char(string="Session Key")
    source = fields.Selection(
        [("detail", "ExchangeDetailServlet"), ("fallback", "ExchangeRateServlet")],
        string="Source",
    )
    state = fields.Selection(
        [
            ("success", "Success (written)"),
            ("waiting", "Waiting (no session yet)"),
            ("stopped_stale", "Stopped - Stale / not listed"),
            ("stopped_failed", "Stopped - Fetch/structure failed"),
            ("stopped_anomaly", "Stopped - Anomaly"),
        ],
        string="State",
        index=True,
    )
    forced = fields.Boolean(string="Forced run")
    message = fields.Char(string="Message")
    raw_json = fields.Text(string="Raw response")
    line_ids = fields.One2many(
        "bidv.exchange.rate.log.line", "log_id", string="Rates"
    )


class BidvExchangeRateLogLine(models.Model):
    _name = "bidv.exchange.rate.log.line"
    _description = "BIDV Exchange Rate Log Line"

    log_id = fields.Many2one(
        "bidv.exchange.rate.log", required=True, ondelete="cascade", index=True
    )
    currency_code = fields.Char(string="Currency")
    value_vnd = fields.Float(string="VND per unit", digits=(16, 4))
    prev_value_vnd = fields.Float(string="Previous VND per unit", digits=(16, 4))
    deviation_pct = fields.Float(string="Deviation %", digits=(16, 2))