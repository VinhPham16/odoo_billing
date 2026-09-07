import json
import logging
import os

import requests

from odoo import api, models
from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot%s/sendMessage"
CONFIG_RELPATH = "config/telegram_config.json"


class BidvTelegram(models.AbstractModel):
    _name = "bidv.telegram"
    _description = "BIDV Telegram Notifier"

    @api.model
    def _get_credentials(self):
        """Ưu tiên ir.config_parameter, fallback đọc file config/telegram_config.json."""
        icp = self.env["ir.config_parameter"].sudo()
        token = icp.get_param("bidv.telegram_token")
        chat_id = icp.get_param("bidv.telegram_chat_id")
        if token and chat_id:
            return token, chat_id

        # Fallback: file config (gitignored)
        module_path = get_module_path("bidv_currency_rate")
        if module_path:
            config_path = os.path.join(module_path, CONFIG_RELPATH)
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    return (
                        token or data.get("token"),
                        chat_id or data.get("chat_id"),
                    )
                except Exception:  # noqa: BLE001 - config lỗi không được làm vỡ pipeline
                    _logger.exception("BIDV: cannot read telegram config file")
        return token, chat_id

    @api.model
    def _send(self, text):
        """Gửi message Telegram. Không raise để không làm vỡ pipeline."""
        token, chat_id = self._get_credentials()
        if not token or not chat_id:
            _logger.warning("BIDV Telegram: missing token/chat_id, skip notify: %s", text)
            return False
        try:
            resp = requests.post(
                TELEGRAM_API % token,
                data={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            ok = resp.ok and resp.json().get("ok")
            if not ok:
                _logger.warning("BIDV Telegram send failed: %s", resp.text)
            return bool(ok)
        except Exception:  # noqa: BLE001
            _logger.exception("BIDV Telegram send error")
            return False