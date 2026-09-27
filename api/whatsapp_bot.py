"""WhatsApp reply bot: a resident messages a ward name and gets that ward's approved heat alert.

Why a reply bot: WhatsApp only lets a business send free text inside a conversation the user
started (and some Twilio test senders accept only templates for outbound messages). Replying
to an incoming message is always a conversation the user started.

Safety rules (same as the rest of Phase 7):
  - the bot only sends text an officer has already APPROVED (status approved or dispatched);
    with no approved alert covering the ward it says so, and sends no model output;
  - requests are accepted only with a valid Twilio signature when TWILIO_AUTH_TOKEN is set;
  - the sender's phone number is never stored: the audit log records ward, language and
    whether an alert was found.

Which alerts: live mode uses alerts dated today or later (the soonest first). With
HEAT_WHATSAPP_REPLAY=<name> (e.g. may2024, for the demo) it uses that replay's alerts, most
recently approved first, so the reply is the alert the officer has just approved.

Message format: "<ward> [english|hindi|gujarati]", e.g. "Vatva", "Vatva gujarati", "AMC-35".
Messages written in Devanagari or Gujarati script get a Hindi or Gujarati reply.
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import hmac
import json
import re
from datetime import date
from xml.sax.saxutils import escape

from api import alerts, db

LANG_WORDS = {"english": "en", "eng": "en", "hindi": "hi", "हिंदी": "hi", "हिन्दी": "hi",
              "gujarati": "gu", "guj": "gu", "ગુજરાતી": "gu"}
LEVEL_ORDER = {"red": 3, "orange": 2, "yellow": 1, "green": 0}
HELP = {
    "en": "Heat alerts for Ahmedabad. Send your ward name, e.g. \"Vatva\" or \"Maninagar gujarati\" "
          "(add hindi or gujarati for other languages).",
    "hi": "अहमदाबाद के लिए लू अलर्ट। अपने वार्ड का नाम भेजें, जैसे \"Vatva hindi\"।",
    "gu": "અમદાવાદ માટે લૂ ચેતવણી. તમારા વોર્ડનું નામ મોકલો, જેમ કે \"Vatva gujarati\".",
}
NO_ALERT = {
    "en": "No heat alert has been issued for {ward} right now. Drink water often and avoid the sun from 12 to 4 pm.",
    "hi": "{ward} के लिए अभी कोई लू अलर्ट जारी नहीं है। पानी पीते रहें और दोपहर 12 से 4 बजे धूप से बचें।",
    "gu": "{ward} માટે હાલ કોઈ લૂ ચેતવણી જારી નથી. પાણી પીતા રહો અને બપોરે 12 થી 4 તડકાથી બચો.",
}
UNKNOWN = {
    "en": "Sorry, I could not find the ward \"{text}\". ",
    "hi": "माफ़ कीजिए, \"{text}\" वार्ड नहीं मिला। ",
    "gu": "માફ કરશો, \"{text}\" વોર્ડ મળ્યો નહીં. ",
}


def valid_signature(auth_token: str, url: str, params: dict, signature: str | None) -> bool:
    """Twilio request signature: HMAC-SHA1 over the full URL plus sorted POST parameters."""
    if not signature:
        return False
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse(text: str, wards: dict[str, str]) -> tuple[str | None, str, str]:
    """-> (ward_id or None, language, leftover text). `wards` maps ward_id → ward name."""
    words = text.strip().split()
    lang = "en"
    if re.search(r"[઀-૿]", text):
        lang = "gu"
    elif re.search(r"[ऀ-ॿ]", text):
        lang = "hi"
    rest = []
    for w in words:
        if w.lower() in LANG_WORDS:
            lang = LANG_WORDS[w.lower()]
        else:
            rest.append(w)
    query = " ".join(rest)
    q = _norm(query)
    if not q:
        return None, lang, query
    m = re.fullmatch(r"(?:amc|ward)?0*(\d{1,2})", q)
    if m and f"AMC-{int(m.group(1)):02d}" in wards:
        return f"AMC-{int(m.group(1)):02d}", lang, query
    by_name = {_norm(n): wid for wid, n in wards.items()}
    if q in by_name:
        return by_name[q], lang, query
    starts = [wid for n, wid in by_name.items() if n.startswith(q) and len(q) >= 4]
    if len(starts) == 1:
        return starts[0], lang, query
    close = difflib.get_close_matches(q, list(by_name), n=1, cutoff=0.8)
    return (by_name[close[0]] if close else None), lang, query


def find_alert(conn, ward_id: str, replay: str | None) -> dict | None:
    """The approved alert to share for a ward (see module docstring)."""
    if replay:
        rows = conn.execute("SELECT alert_id, wards, level FROM alerts WHERE mode='replay' AND replay=? AND "
                            "status IN ('approved','dispatched') ORDER BY decided_at DESC, alert_id DESC", (replay,)).fetchall()
    else:
        rows = conn.execute("SELECT alert_id, wards, level FROM alerts WHERE mode='live' AND date>=? AND "
                            "status IN ('approved','dispatched') ORDER BY date, alert_id", (date.today().isoformat(),)).fetchall()
    hits = [r for r in rows if ward_id in json.loads(r["wards"])]
    if not hits:
        return None
    if not replay:          # soonest day first; on the same day the most severe
        first_day = alerts.load(conn, hits[0]["alert_id"])["date"]
        same = [r for r in hits if alerts.load(conn, r["alert_id"])["date"] == first_day]
        hits = sorted(same, key=lambda r: -LEVEL_ORDER.get(r["level"], 0))
    return alerts.load(conn, hits[0]["alert_id"])


def reply(conn, text: str, replay: str | None) -> tuple[str, dict]:
    """-> (reply text, audit detail without any phone number)."""
    wards = dict(conn.execute("SELECT ward_id, ward_name FROM wards").fetchall())
    ward_id, lang, query = parse(text, wards)
    if not query or _norm(query) in ("hi", "hello", "help", "start", "namaste"):
        return HELP[lang], {"query": "help", "lang": lang}
    if ward_id is None:
        return UNKNOWN[lang].format(text=query[:40]) + HELP[lang], {"query": "unknown", "lang": lang}
    a = find_alert(conn, ward_id, replay)
    if a is None or lang not in a["languages"] or "public" not in a["templates"].get(lang, {}):
        return NO_ALERT[lang].format(ward=wards[ward_id]), {"ward_id": ward_id, "lang": lang, "alert_id": None}
    msg = alerts.render(a, ward_id, lang, "public")["long"]
    return msg, {"ward_id": ward_id, "lang": lang, "alert_id": a["alert_id"], "level": a["level"]}


def twiml(text: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(text)}</Message></Response>'


def handle(params: dict, replay: str | None) -> str:
    with db.connect() as conn:
        text, detail = reply(conn, params.get("Body", ""), replay)
        db.log(conn, "whatsapp_reply", detail, actor="whatsapp_bot")
    return twiml(text)
