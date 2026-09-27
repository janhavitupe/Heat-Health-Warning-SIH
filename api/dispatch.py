"""Alert delivery (Phase 7): SMS, WhatsApp and voice, simulated unless explicitly configured.

Default mode is **simulated**: every message that would be sent is rendered and recorded in
the deliveries table and audit log, and nothing leaves the machine.

Real sending through the Twilio sandbox needs:
  HEAT_DISPATCH_MODE=twilio
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
  a sender for each channel used in the recipients file: TWILIO_SMS_FROM, TWILIO_VOICE_FROM (a Twilio
  number) and/or TWILIO_WHATSAPP_FROM (the free WhatsApp sandbox: the number shown in your Twilio Console, e.g. whatsapp:+1XXXXXXXXXX)
  data/manual/test_recipients.csv  (your own verified test numbers; the example file is never
                                    used for real sending)
  optional HEAT_PUBLIC_URL          (public address of this API, for the voice keypad menu)

Recipients file columns: name, phone, channel (sms|whatsapp|voice), lang (en|hi|gu),
audience (public|workers|elderly), ward_id (a ward id, or * for the alert's highest-risk ward).
Only an approved alert can be dispatched; api/alerts.py enforces that before calling here.
"""

from __future__ import annotations

import os

import pandas as pd
import requests

from api import alerts, db
from heatrisk.config import ROOT

RECIPIENTS = ROOT / "data" / "manual" / "test_recipients.csv"
EXAMPLE = ROOT / "data" / "manual" / "test_recipients.example.csv"
TWILIO = "https://api.twilio.com/2010-04-01/Accounts/{sid}"


def mode() -> str:
    return "twilio" if os.environ.get("HEAT_DISPATCH_MODE") == "twilio" else "simulated"


def recipients() -> pd.DataFrame:
    if mode() == "twilio":
        if not RECIPIENTS.exists():
            raise alerts.WorkflowError("Twilio mode needs data/manual/test_recipients.csv with verified test numbers")
        return pd.read_csv(RECIPIENTS, dtype=str)
    return pd.read_csv(RECIPIENTS if RECIPIENTS.exists() else EXAMPLE, dtype=str)


SENDER = {"sms": "TWILIO_SMS_FROM", "whatsapp": "TWILIO_WHATSAPP_FROM", "voice": "TWILIO_VOICE_FROM"}


def _twilio_env(channels) -> dict:
    """Credentials plus a sender for each channel actually used (trial accounts may have only WhatsApp)."""
    need = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"] + sorted({SENDER[c] for c in channels if c in SENDER})
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        raise alerts.WorkflowError(f"Twilio mode is missing environment variables: {missing}")
    return {k: os.environ[k] for k in need}


def _send_twilio(env: dict, channel: str, phone: str, body: str, voice_xml: str) -> tuple[str, str, str]:
    base, auth = TWILIO.format(sid=env["TWILIO_ACCOUNT_SID"]), (env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"])
    if channel == "voice":
        r = requests.post(f"{base}/Calls.json", auth=auth, timeout=30,
                          data={"To": phone, "From": env["TWILIO_VOICE_FROM"], "Twiml": voice_xml})
    else:
        frm = env["TWILIO_WHATSAPP_FROM"] if channel == "whatsapp" else env["TWILIO_SMS_FROM"]
        to = f"whatsapp:{phone}" if channel == "whatsapp" else phone
        r = requests.post(f"{base}/Messages.json", auth=auth, timeout=30, data={"To": to, "From": frm, "Body": body})
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400:
        used = env["TWILIO_VOICE_FROM"] if channel == "voice" else frm
        return "failed", j.get("sid", ""), f"{j.get('message', r.text[:200])} (Twilio error {j.get('code', r.status_code)}; from {used})"
    return j.get("status", "queued"), j.get("sid", ""), ""


def dispatch(conn, alert_id: int, officer: str) -> dict:
    officer = alerts._officer(officer)
    a = alerts.load(conn, alert_id)
    alerts._require(a, "approved", "dispatch")
    m = mode()
    rec = recipients()
    used = [c for c in rec["channel"].unique() if c in a["channels"]]
    env = _twilio_env(used) if m == "twilio" else None
    base_url = os.environ.get("HEAT_PUBLIC_URL")
    rows = []
    for r in rec.itertuples():
        if r.channel not in a["channels"] or r.lang not in a["languages"] or r.audience not in a["audiences"]:
            continue
        ward = a["wards"][0] if r.ward_id == "*" else r.ward_id
        if ward not in a["wards"]:
            continue
        msg = alerts.render(a, ward, r.lang, r.audience)
        body = msg["long"] if r.channel in ("voice", "whatsapp") else msg["sms"]
        voice_xml = alerts.twiml(a, ward, r.lang, r.audience, base_url=base_url) if r.channel == "voice" else ""
        if m == "twilio":
            status, sid, detail = _send_twilio(env, r.channel, r.phone, body, voice_xml)
        else:
            status, sid, detail = "simulated", "", "not sent: simulation mode"
        rows.append((alert_id, ward, r.channel, r.phone, r.audience, r.lang, body, status, m, sid, detail, db.now()))
    conn.executemany("INSERT INTO deliveries (alert_id, ward_id, channel, recipient, audience, lang, body, status, "
                     "provider, provider_id, detail, at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("UPDATE alerts SET status='dispatched', dispatched_at=? WHERE alert_id=?", (db.now(), alert_id))
    counts = pd.Series([row[7] for row in rows]).value_counts().to_dict() if rows else {}
    db.log(conn, "alert_dispatched", {"alert_id": alert_id, "mode": m, "messages": len(rows), "status": counts},
           actor=officer)
    return {"alert_id": alert_id, "mode": m, "messages": len(rows), "status": counts}


def refresh_status(conn, alert_id: int) -> int:
    """Twilio mode: fetch the latest delivery status of each message/call and record changes."""
    if mode() != "twilio":
        return 0
    env = _twilio_env([])                   # status lookups need only the credentials
    base, auth = TWILIO.format(sid=env["TWILIO_ACCOUNT_SID"]), (env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"])
    changed = 0
    for d in conn.execute("SELECT id, channel, provider_id, status FROM deliveries WHERE alert_id=? AND provider='twilio' "
                          "AND provider_id<>''", (alert_id,)).fetchall():
        kind = "Calls" if d["channel"] == "voice" else "Messages"
        r = requests.get(f"{base}/{kind}/{d['provider_id']}.json", auth=auth, timeout=30)
        new = r.json().get("status") if r.ok else None
        if new and new != d["status"]:
            conn.execute("UPDATE deliveries SET status=?, at=? WHERE id=?", (new, db.now(), d["id"]))
            db.log(conn, "delivery_status", {"delivery_id": d["id"], "status": new})
            changed += 1
    return changed


if __name__ == "__main__":        # quick check of the configured mode and recipients
    print("mode:", mode(), "| recipients:", len(recipients()), "| file:",
          RECIPIENTS if RECIPIENTS.exists() else EXAMPLE, "| public url:", os.environ.get("HEAT_PUBLIC_URL"))
