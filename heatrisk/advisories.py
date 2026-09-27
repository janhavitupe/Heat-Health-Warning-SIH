"""Public Advisory Generator (Phase 6).

Fills the templates in resources/advisories.yaml for one ward-day: three audiences
(public, outdoor workers, elderly/caregivers) × alert level × language (en/hi/gu),
as a short SMS and a longer WhatsApp text (also used as the voice script in Phase 7).
Green days produce no advisory. Hindi and Gujarati templates are drafts pending
native-speaker verification; every advisory carries its review status.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
import yaml

from heatrisk.config import ROOT

TEMPLATES = ROOT / "resources" / "advisories.yaml"
AUDIENCES = ("public", "workers", "elderly")
LANGS = ("en", "hi", "gu")
SMS_LIMIT = {"en": 160, "hi": 134, "gu": 134}      # one GSM-7 SMS; two Unicode SMS parts
STATUS_KEY = {"not_advised": "not_advised", "15/45": "rest_45", "30/30": "rest_30", "45/15": "rest_15"}


@lru_cache(maxsize=1)
def load_templates(path: str = str(TEMPLATES)) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _day_text(date, lang: str) -> str:
    d = pd.Timestamp(date)
    return d.strftime("%a %d %b") if lang == "en" else d.strftime("%d/%m")


def heavy_window(schedule: dict | None) -> str:
    """Widest heavy-work "not advised" interval, else the first restricted interval, e.g. "11:00-16:00"."""
    ivs = (schedule or {}).get("workloads", {}).get("heavy", {}).get("restricted", [])
    pick = [iv for iv in ivs if iv["status"] == "not_advised"] or ivs
    if not pick:
        return "12-4pm"
    return f"{pick[0]['start']}-{pick[-1]['end']}"


def work_summary(schedule: dict | None, lang: str) -> str:
    phrases = load_templates()["work_phrases"][lang]
    ivs = (schedule or {}).get("workloads", {}).get("heavy", {}).get("restricted", [])
    if not ivs:
        return phrases["none"]
    parts: dict[str, list[str]] = {}
    for iv in ivs:
        parts.setdefault(STATUS_KEY[iv["status"]], []).append(f"{iv['start']}-{iv['end']}")
    order = ["not_advised", "rest_45", "rest_30", "rest_15"]
    return "; ".join(f"{phrases[k]} {', '.join(parts[k])}" for k in order if k in parts)


def short_place(name: str, limit: int = 24) -> str:
    """Shorten a place name for SMS at a word boundary. No "…": one non-GSM character would switch an
    English SMS to Unicode encoding and cut its limit from 160 to 70 characters."""
    if len(name) <= limit:
        return name
    cut = name[:limit]
    return cut[: cut.rfind(" ")] if " " in cut else cut       # whole words only, no ellipsis


def values(ward_name: str, date, level: str, lang: str, schedule: dict | None = None,
           cooling: list[dict] | None = None, peak: str | None = None, sender: str = "AMC") -> dict:
    """Placeholder values for one ward-day in one language."""
    t = load_templates()
    places = [p["name"] for p in (cooling or [])]
    return {
        "level": t["level_names"][lang][level], "ward": ward_name, "day": _day_text(date, lang), "sender": sender,
        "window": heavy_window(schedule), "cooling": short_place(places[0]) if places else "nearest UHC",
        "cooling_list": ", ".join(places) if places else "—", "peak": (peak or "15:00").split("–")[0],
        "work_summary": work_summary(schedule, lang),
    }


def templates(level: str, lang: str, audience: str) -> dict:
    """The SMS and long-text templates (with {placeholders}) for one level, language and audience."""
    t = load_templates()
    long = t["long"][lang]
    return {"sms": t["sms"][lang][audience][level],
            "long": " ".join([long["headline"], long["facts"], long[audience]])}


class _Keep(dict):
    def __missing__(self, key):                     # unknown placeholder: leave it visible for the reviewer
        return "{" + key + "}"


def fill(template: str, vals: dict) -> str:
    return template.format_map(_Keep(vals))


def render(ward_name: str, date, level: str, lang: str, audience: str, schedule: dict | None = None,
           cooling: list[dict] | None = None, peak: str | None = None, sender: str = "AMC",
           template: dict | None = None) -> dict | None:
    """One advisory (SMS + long text) or None on Green days. `template` overrides the default text."""
    if level not in ("yellow", "orange", "red"):
        return None
    vals = values(ward_name, date, level, lang, schedule, cooling, peak, sender)
    tpl = template or templates(level, lang, audience)
    sms, text = fill(tpl["sms"], vals), fill(tpl["long"], vals)
    return {"lang": lang, "audience": audience, "level": level, "sms": sms, "sms_chars": len(sms),
            "sms_fits": len(sms) <= SMS_LIMIT[lang], "long": text,
            "review_status": load_templates()["review_status"][lang]}


def render_all(ward_name: str, date, level: str, **kwargs) -> list[dict]:
    """Every audience × language for one ward-day (empty on Green days)."""
    out = [render(ward_name, date, level, lang, aud, **kwargs) for lang in LANGS for aud in AUDIENCES]
    return [a for a in out if a]
