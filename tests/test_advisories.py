import pytest

from heatrisk import advisories as adv

LONGEST_WARD = "Bhaipura Hatkeshwar"           # longest 2015 ward name
SCHEDULE = {"workloads": {"heavy": {"restricted": [
    {"status": "30/30", "start": "08:00", "end": "09:00"},
    {"status": "not_advised", "start": "09:00", "end": "16:00"},
    {"status": "30/30", "start": "16:00", "end": "18:00"}]}}}
COOLING = [{"name": "Sardar Vallabhbhai Patel Institute of Medical Sciences and Research (SVP)", "layer": "public_hospital"}]


@pytest.mark.parametrize("lang", adv.LANGS)
@pytest.mark.parametrize("audience", adv.AUDIENCES)
@pytest.mark.parametrize("level", ["yellow", "orange", "red"])
def test_every_sms_fits_with_longest_names(lang, audience, level):
    a = adv.render(LONGEST_WARD, "2024-05-23", level, lang, audience, SCHEDULE, COOLING, "14:00–15:00")
    assert a["sms_fits"], f"{lang}/{audience}/{level}: {a['sms_chars']} chars: {a['sms']}"
    assert "{" not in a["sms"] and "{" not in a["long"]            # every placeholder filled
    assert "108" in a["sms"]


def test_green_days_have_no_advisory():
    assert adv.render_all("Odhav", "2024-05-01", "green") == []


def test_worker_advice_uses_the_work_window():
    a = adv.render("Odhav", "2024-05-23", "red", "en", "workers", SCHEDULE)
    assert "09:00-16:00" in a["sms"]
    assert "not advised 09:00-16:00; 30 min rest per hour 08:00-09:00, 16:00-18:00" in a["long"]


def test_translations_flagged_for_review():
    items = adv.render_all("Odhav", "2024-05-23", "red", schedule=SCHEDULE, cooling=COOLING)
    assert len(items) == 9
    assert {a["review_status"] for a in items if a["lang"] != "en"} == {"draft_needs_native_review"}


GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")


@pytest.mark.parametrize("audience", adv.AUDIENCES)
@pytest.mark.parametrize("level", ["yellow", "orange", "red"])
def test_english_sms_uses_only_gsm_characters(audience, level):
    """A single non-GSM character would switch the SMS to Unicode (70-character parts)."""
    a = adv.render(LONGEST_WARD, "2024-05-23", level, "en", audience, SCHEDULE, COOLING, "14:00–15:00")
    assert set(a["sms"]) <= GSM7, set(a["sms"]) - GSM7
