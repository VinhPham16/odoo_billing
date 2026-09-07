from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bidv_enabled = fields.Boolean(
        string="Bật lấy tỷ giá BIDV",
        config_parameter="bidv.enabled",
        default=True,
    )
    bidv_currencies = fields.Char(
        string="Currencies (rỗng = mọi currency active)",
        help="Danh sách mã tiền tệ, phân tách bằng dấu phẩy. Ví dụ: USD,EUR",
        config_parameter="bidv.currencies",
    )
    bidv_anomaly_threshold = fields.Float(
        string="Ngưỡng bất thường (%)",
        config_parameter="bidv.anomaly_threshold",
        default=5.0,
    )
    bidv_window_start = fields.Char(
        string="Cửa sổ bắt đầu (HH:MM, giờ VN)",
        config_parameter="bidv.window_start",
        default="08:00",
    )
    bidv_window_end = fields.Char(
        string="Cửa sổ kết thúc (HH:MM, giờ VN)",
        config_parameter="bidv.window_end",
        default="10:00",
    )
    bidv_skip_weekend = fields.Boolean(
        string="Bỏ qua cuối tuần (T7/CN)",
        config_parameter="bidv.skip_weekend",
        default=True,
    )
    bidv_telegram_token = fields.Char(
        string="Telegram Bot Token",
        config_parameter="bidv.telegram_token",
    )
    bidv_telegram_chat_id = fields.Char(
        string="Telegram Chat ID",
        config_parameter="bidv.telegram_chat_id",
    )

    def action_bidv_run_force(self):
        self.ensure_one()
        state = self.env["bidv.rate.service"].action_run_force()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "BIDV",
                "message": "Kết quả chạy tay (force): %s" % state,
                "type": "success" if state == "success" else "warning",
                "sticky": False,
            },
        }