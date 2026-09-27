"""WhatsApp reply bot: parsing, Twilio signature check."""

from api import whatsapp_bot as bot

WARDS = {"AMC-35": "Baherampura", "AMC-47": "Vatva", "AMC-29": "Maninagar", "AMC-06": "New Wadaj", "AMC-48": "Vasna"}


def test_parse_ward_and_language():
    assert bot.parse("Vatva", WARDS) == ("AMC-47", "en", "Vatva")
    assert bot.parse("vatva GUJARATI", WARDS)[:2] == ("AMC-47", "gu")
    assert bot.parse("new wadaj hindi", WARDS)[:2] == ("AMC-06", "hi")
    assert bot.parse("Baherampur", WARDS)[0] == "AMC-35"          # typo / prefix
    assert bot.parse("ward 35", WARDS)[0] == "AMC-35" and bot.parse("AMC-47", WARDS)[0] == "AMC-47"
    assert bot.parse("Vasn", WARDS)[0] == "AMC-48"                  # unique prefix of 4+ letters
    assert bot.parse("Va", WARDS)[0] is None and bot.parse("Xyzabc", WARDS)[0] is None
    assert bot.parse("વટવા", WARDS)[1] == "gu"                      # Gujarati script → Gujarati reply


def test_twilio_signature_matches_documented_example():
    # Example from Twilio's "Webhooks security" documentation
    params = {"CallSid": "CA1234567890ABCDE", "Caller": "+12349013030", "Digits": "1234",
              "From": "+12349013030", "To": "+18005551212"}
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    assert bot.valid_signature("12345", url, params, "0/KCTR6DLpKmkAf8muzZqo1nDgQ=")
    assert not bot.valid_signature("12345", url, {**params, "Digits": "9"}, "0/KCTR6DLpKmkAf8muzZqo1nDgQ=")
    assert not bot.valid_signature("12345", url, params, None)


def test_reply_is_xml_escaped():
    assert "&lt;b&gt;" in bot.twiml("<b>") and bot.twiml("x").startswith("<?xml")
