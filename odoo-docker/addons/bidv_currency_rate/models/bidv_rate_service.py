import json
import logging
from datetime import datetime

import pytz
import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

URL_SEARCH_TIME = "https://bidv.com.vn/ServicesBIDV/ExchangeDetailSearchTimeServlet"
URL_DETAIL = "https://bidv.com.vn/ServicesBIDV/ExchangeDetailServlet"
URL_RATE = "https://bidv.com.vn/ServicesBIDV/ExchangeRateServlet"
HTTP_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OdooBidvCurrencyRate/1.0"

# ir.config_parameter keys + defaults
P_ENABLED = "bidv.enabled"
P_CURRENCIES = "bidv.currencies"          # "USD,EUR" ; rỗng = mọi currency active
P_THRESHOLD = "bidv.anomaly_threshold"    # phần trăm, mặc định "5"
P_WINDOW_START = "bidv.window_start"       # "08:00"
P_WINDOW_END = "bidv.window_end"           # "10:00"
P_SKIP_WEEKEND = "bidv.skip_weekend"       # "1"
P_LAST_NAMERECORD = "bidv.last_namerecord"
P_LAST_STALE_NOTIFY = "bidv.last_stale_notify_date"


class BidvRateService(models.AbstractModel):
    _name = "bidv.rate.service"
    _description = "BIDV Currency Rate Service"

    # ----------------------------------------------------------------- helpers
    @api.model
    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def _as_bool(self, value, default=True):
        # ir.config_parameter.get_param trả về False (không phải None) khi key chưa tồn tại,
        # nên coi cả None/False/"" là "chưa set -> dùng default".
        if value is None or value is False or value == "":
            return default
        return str(value).strip().lower() in ("1", "true", "yes")

    @api.model
    def _get_config(self):
        icp = self._icp()
        codes = (icp.get_param(P_CURRENCIES) or "").strip()
        return {
            "enabled": self._as_bool(icp.get_param(P_ENABLED, "True"), default=True),
            "currencies": [c.strip().upper() for c in codes.split(",") if c.strip()],
            "threshold": float(icp.get_param(P_THRESHOLD, "5") or 5),
            "window_start": icp.get_param(P_WINDOW_START, "08:00") or "08:00",
            "window_end": icp.get_param(P_WINDOW_END, "10:00") or "10:00",
            "skip_weekend": self._as_bool(icp.get_param(P_SKIP_WEEKEND, "True"), default=True),
        }

    @api.model
    def _vn_now(self):
        return datetime.now(VN_TZ)

    @api.model
    def _parse_hhmm(self, value, default_h, default_m):
        try:
            parts = (value or "").split(":")
            return int(parts[0]), int(parts[1])
        except Exception:  # noqa: BLE001
            return default_h, default_m

    @api.model
    def _to_bidv_date(self, d):
        return d.strftime("%d/%m/%Y")

    @api.model
    def _clean_number(self, raw):
        """'25,890' -> 25890.0 ; '160.22' -> 160.22 ; '-'/'' -> None. Không dùng re."""
        if raw is None:
            return None
        text = str(raw).replace(",", "").replace(" ", "").strip()
        if not text or text == "-":
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @api.model
    def _active_currency_map(self, config):
        """{code: recordset} các currency active (trừ currency công ty), giao với cấu hình."""
        company = self.env.company
        active = self.env["res.currency"].search([("active", "=", True)])
        cfg = set(config["currencies"])
        result = {}
        for cur in active:
            if cur == company.currency_id:
                continue
            code = (cur.name or "").upper()
            if cfg and code not in cfg:
                continue
            result[code] = cur
        return result

    # -------------------------------------------------------------- HTTP calls
    @api.model
    def _http_post(self, url, data):
        resp = requests.post(
            url, data=data, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )
        resp.raise_for_status()
        return resp.json()

    @api.model
    def _http_get(self, url):
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return resp.json()

    @api.model
    def _get_opening_session(self, d):
        """Trả (namerecord, hour) của phiên mở cửa (time==1) hoặc None nếu chưa niêm yết."""
        payload = self._http_post(URL_SEARCH_TIME, {"date": self._to_bidv_date(d)})
        if not payload or payload.get("status") != 1:
            return None
        sessions = payload.get("data") or []
        if not sessions:
            return None
        opening = None
        for s in sessions:
            if s.get("time") == 1:
                opening = s
                break
        if opening is None:
            # fallback: phiên có giờ sớm nhất
            opening = sorted(sessions, key=lambda s: s.get("hour") or "99:99")[0]
        return opening.get("namerecord"), opening.get("hour"), payload

    @api.model
    def _fetch_detail(self, d, namerecord):
        payload = self._http_post(
            URL_DETAIL, {"date": self._to_bidv_date(d), "time": namerecord}
        )
        rows = (payload or {}).get("data") or []
        return rows, payload

    @api.model
    def _fetch_current_fallback(self):
        payload = self._http_get(URL_RATE) or {}
        rows = payload.get("data") or []
        # ExchangeRateServlet dùng key khác: mua_ck_value (số sẵn), currency
        norm = []
        for r in rows:
            norm.append({
                "currency": r.get("currency"),
                "muaCk": r.get("mua_ck") or r.get("mua_ck_value"),
                "muaCk_value": r.get("mua_ck_value"),
            })
        return norm, payload

    # ----------------------------------------------------------------- parsing
    @api.model
    def _parse_rows(self, rows, cur_map, source):
        """Lọc currency active + làm sạch số. Trả (rates, missing)."""
        rates = {}
        for r in rows:
            code = (r.get("currency") or "").upper()
            if code not in cur_map:
                continue  # bỏ currency không active + dòng biến thể USD(1-2-5)...
            if source == "fallback" and r.get("muaCk_value") is not None:
                value = self._clean_number(r.get("muaCk_value"))
            else:
                value = self._clean_number(r.get("muaCk"))
            if value is None or value <= 0:
                continue
            rates[code] = value
        missing = [c for c in cur_map if c not in rates]
        return rates, missing

    # --------------------------------------------------------------- anomaly
    @api.model
    def _prev_value(self, currency, d):
        rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", currency.id),
                ("company_id", "=", self.env.company.id),
                ("name", "<", fields.Date.to_string(d)),
            ],
            order="name desc",
            limit=1,
        )
        return rate.inverse_company_rate if rate else None

    @api.model
    def _check_anomaly(self, rates, cur_map, d, threshold):
        """Trả list dict lệch > ngưỡng: [{code, new, prev, pct}]."""
        anomalies = []
        for code, value in rates.items():
            prev = self._prev_value(cur_map[code], d)
            if not prev:
                continue
            pct = abs(value - prev) / prev * 100.0
            if pct > threshold:
                anomalies.append({"code": code, "new": value, "prev": prev, "pct": pct})
        return anomalies

    # ----------------------------------------------------------------- write
    @api.model
    def _write_rates(self, rates, cur_map, d):
        Rate = self.env["res.currency.rate"]
        company = self.env.company
        for code, value in rates.items():
            currency = cur_map[code]
            existing = Rate.search(
                [
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", company.id),
                    ("name", "=", fields.Date.to_string(d)),
                ],
                limit=1,
            )
            vals = {"inverse_company_rate": value}
            if existing:
                existing.write(vals)
            else:
                Rate.create({
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": fields.Date.to_string(d),
                    **vals,
                })

    @api.model
    def _already_done(self, cur_map, d):
        """True nếu đã có rate hôm nay cho tất cả currency active."""
        Rate = self.env["res.currency.rate"]
        company = self.env.company
        for currency in cur_map.values():
            if not Rate.search_count([
                ("currency_id", "=", currency.id),
                ("company_id", "=", company.id),
                ("name", "=", fields.Date.to_string(d)),
            ]):
                return False
        return bool(cur_map)

    # ----------------------------------------------------------------- logging
    @api.model
    def _log(self, state, d, message="", provider_day=False, provider_hour=False,
             namerecord=False, source=False, forced=False, raw=None,
             rates=None, cur_map=None, anomalies=None):
        line_vals = []
        if rates:
            anomaly_map = {a["code"]: a for a in (anomalies or [])}
            for code, value in rates.items():
                a = anomaly_map.get(code)
                line_vals.append((0, 0, {
                    "currency_code": code,
                    "value_vnd": value,
                    "prev_value_vnd": a["prev"] if a else 0.0,
                    "deviation_pct": a["pct"] if a else 0.0,
                }))
        return self.env["bidv.exchange.rate.log"].create({
            "date": d,
            "state": state,
            "message": message,
            "provider_day": provider_day,
            "provider_hour": provider_hour,
            "namerecord": str(namerecord) if namerecord else False,
            "source": source,
            "forced": forced,
            "raw_json": json.dumps(raw, ensure_ascii=False) if raw is not None else False,
            "line_ids": line_vals,
        })

    @api.model
    def _notify(self, text):
        self.env["bidv.telegram"]._send(text)

    # --------------------------------------------------------------- pipeline
    @api.model
    def _run(self, date=None, force=False, allow_waiting=False):
        config = self._get_config()
        if not config["enabled"] and not force:
            return "disabled"

        d = date or self._vn_now().date()
        cur_map = self._active_currency_map(config)
        if not cur_map:
            self._log("stopped_failed", d, message="Không có currency active để lấy tỷ giá")
            return "no_currency"

        if not force and self._already_done(cur_map, d):
            return "already_done"

        # 1) SearchTime -> phiên mở cửa
        try:
            session = self._get_opening_session(d)
        except Exception as e:  # noqa: BLE001
            self._log("stopped_failed", d, message="SearchTime lỗi: %s" % e)
            self._notify("[BIDV] Lỗi gọi SearchTime %s: %s" % (self._to_bidv_date(d), e))
            return "stopped_failed"

        if not session:
            if allow_waiting:
                self._log("waiting", d, message="Chưa có phiên niêm yết")
                return "waiting"
            if self._icp().get_param(P_LAST_STALE_NOTIFY) != fields.Date.to_string(d):
                self._notify("[BIDV] %s: hết cửa sổ vẫn chưa có phiên niêm yết" % self._to_bidv_date(d))
                self._icp().set_param(P_LAST_STALE_NOTIFY, fields.Date.to_string(d))
            self._log("stopped_stale", d, message="Chưa niêm yết đến cuối cửa sổ")
            return "stopped_stale"

        namerecord, hour, search_raw = session

        # stale: namerecord trùng phiên đã ghi trước đó (không có phiên mới)
        if not force and str(namerecord) == (self._icp().get_param(P_LAST_NAMERECORD) or ""):
            self._log("stopped_stale", d, message="namerecord trùng - không có phiên mới",
                      namerecord=namerecord, provider_hour=hour, raw=search_raw)
            self._notify("[BIDV] %s: namerecord %s trùng, không có phiên mới" % (
                self._to_bidv_date(d), namerecord))
            return "stopped_stale"

        # 2) Detail (fallback Rate)
        source = "detail"
        try:
            rows, raw = self._fetch_detail(d, namerecord)
            if not rows:
                raise ValueError("Detail rỗng")
        except Exception as e:  # noqa: BLE001
            _logger.warning("BIDV Detail lỗi, thử fallback: %s", e)
            try:
                rows, raw = self._fetch_current_fallback()
                source = "fallback"
                if not rows:
                    raise ValueError("Fallback rỗng")
            except Exception as e2:  # noqa: BLE001
                self._log("stopped_failed", d, message="Detail & fallback lỗi: %s / %s" % (e, e2),
                          namerecord=namerecord, provider_hour=hour)
                self._notify("[BIDV] %s: lỗi lấy bảng tỷ giá (Detail & fallback)" % self._to_bidv_date(d))
                return "stopped_failed"

        # 3) parse + lọc active + guard cấu trúc
        rates, missing = self._parse_rows(rows, cur_map, source)
        if missing:
            self._log("stopped_failed", d,
                      message="Thiếu currency active: %s" % ", ".join(missing),
                      namerecord=namerecord, provider_hour=hour, source=source, raw=raw,
                      rates=rates, cur_map=cur_map)
            self._notify("[BIDV] %s: thiếu tỷ giá currency %s" % (
                self._to_bidv_date(d), ", ".join(missing)))
            return "stopped_failed"

        # 4) anomaly (bỏ qua nếu force)
        anomalies = [] if force else self._check_anomaly(rates, cur_map, d, config["threshold"])
        if anomalies:
            detail = "; ".join("%s %.2f%% (%.4f→%.4f)" % (
                a["code"], a["pct"], a["prev"], a["new"]) for a in anomalies)
            self._log("stopped_anomaly", d, message="Anomaly: %s" % detail,
                      namerecord=namerecord, provider_hour=hour, source=source, raw=raw,
                      rates=rates, cur_map=cur_map, anomalies=anomalies)
            self._notify("[BIDV] %s: PHÁT HIỆN BẤT THƯỜNG >%.0f%%\n%s\nChạy lại force nếu xác nhận đúng." % (
                self._to_bidv_date(d), config["threshold"], detail))
            return "stopped_anomaly"

        # 5) GHI
        self._write_rates(rates, cur_map, d)
        self._icp().set_param(P_LAST_NAMERECORD, str(namerecord))
        self._log("success", d, message="Ghi %d tỷ giá%s" % (len(rates), " (forced)" if force else ""),
                  namerecord=namerecord, provider_hour=hour, source=source, forced=force,
                  raw=raw, rates=rates, cur_map=cur_map)
        return "success"

    # ------------------------------------------------------------------- cron
    @api.model
    def _cron_run(self):
        config = self._get_config()
        if not config["enabled"]:
            return
        now = self._vn_now()
        if config["skip_weekend"] and now.weekday() >= 5:  # 5=T7, 6=CN
            return
        sh, sm = self._parse_hhmm(config["window_start"], 8, 0)
        eh, em = self._parse_hhmm(config["window_end"], 10, 0)
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if now < start:
            return  # chưa tới cửa sổ
        if (now - end).total_seconds() > 30 * 60:
            return  # đã quá cuối cửa sổ > 30' -> ngừng poll ngày đó
        # Trong cửa sổ -> allow_waiting (im lặng chờ). Sau end (trong 30') -> lần chốt: noti stale.
        allow_waiting = now <= end
        self._run(force=False, allow_waiting=allow_waiting)

    # --------------------------------------------------------- manual (force)
    @api.model
    def action_run_force(self):
        state = self._run(force=True, allow_waiting=False)
        return state