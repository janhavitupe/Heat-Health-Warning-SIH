# Command Dashboard and Alert Delivery (Phase 7)

Phase 7 takes an alert from automatic trigger to human review, approval and dispatch, with every step recorded. Code: [api/alerts.py](../api/alerts.py) (engine, workflow, CAP, voice), [api/dispatch.py](../api/dispatch.py) (delivery), [api/main.py](../api/main.py) (endpoints), [frontend/src/components/AlertsTab.jsx](../frontend/src/components/AlertsTab.jsx) and [StatusStrip.jsx](../frontend/src/components/StatusStrip.jsx).

## Safety rules (enforced in code, covered by tests)

1. **Nothing is sent without explicit approval.** Only an alert with status *approved* can be dispatched.
2. **Every decision carries an officer's name.** Approval and rejection refuse a blank name, and rejection also needs a reason.
3. **Approved alerts are frozen.** Editing, approving again or dispatching twice are refused.
4. **Every step is audited:** drafted, edited (with what changed), approved, rejected, dispatched (with counts), and delivery status updates.
5. **Delivery is simulated by default.** The system renders and records every message it *would* send, and nothing leaves the machine. Real sending needs deliberate setup (see below) and refuses to use the example recipient list.
6. **Write access can be locked.** When `HEAT_API_TOKEN` is set, every write action needs the `X-API-Token` header. Set it whenever the app is reachable by anyone else.

## Workflow

```
forecast / replay run ──► Alert Engine ──► draft ──► officer edits ──► approve ──► dispatch ──► deliveries
                                             │                       └► reject (reason)
                                             └► superseded (when more wards join before review)
```

- **Engine:** one draft per day per level (Orange, Red), listing the wards at that level, most at-risk first. In live mode, probability triggers (P(Red) ≥ 40% within 3 days) also create *preparedness* drafts. The scheduler drafts after every refresh.
- **No duplicates:** running the engine again adds nothing. If more wards reach the level before review, the draft is replaced by one covering all of them. If the day's alert was already approved, a new draft covers only the extra wards and is exported as a CAP *Update*.
- **Messages:** each alert stores editable **templates** per language and audience (e.g. `{level} {day}, {ward}: … Call 108 -{sender}`) plus each ward's **values**, captured when drafted (day, heavy-work window, hottest hour, nearest cooling places). One edit applies to every ward, and approval is blocked if any rendered SMS is too long.
- **Officer choices:** remove wards, and choose audiences (public, outdoor workers, elderly and caregivers), languages (English, Hindi, Gujarati) and channels (SMS, WhatsApp, voice).

## CAP 1.2 export

`GET /alerts/{id}/cap.xml` produces a Common Alerting Protocol 1.2 message, the standard behind India's NDMA Sachet platform. **It is validated against the official OASIS CAP 1.2 schema in the tests.**

| CAP field | Value |
|---|---|
| status | Draft (not approved) · Exercise (replay) · Actual (approved live alert) |
| msgType | Alert, or Update with `<references>` to the earlier alert |
| severity | Yellow → Moderate, Orange → Severe, Red → Extreme |
| urgency | alert day is today → Immediate, tomorrow → Expected, later → Future |
| certainty | Likely if the median ward's forecast probability of the level is ≥ 50% (the CAP definition), otherwise Possible |
| responseType | Orange → Prepare, Red → Avoid |
| info | one block per language (en-IN, hi-IN, gu-IN), categories Met and Health, public advice as `<instruction>` |
| area | one per ward, with the outline simplified to 50 m as `<polygon>` |

The `<sender>` is a placeholder (`heat-alert-prototype@example.invalid`, set in `config.yaml`). The issuing authority must set its own; the prototype doesn't claim to speak for any organisation.

## Voice (IVR)

`/ivr/{alert}/{ward}?lang=` returns Twilio TwiML that reads the WhatsApp/voice text using Google voices for `en-IN`, `hi-IN` and `gu-IN`. Twilio supports Gujarati and Hindi Google voices. The keypad menu offers **1** to repeat and **2** to hear the nearest cooling places. Without a public callback address, the message is played twice instead. The Hindi and Gujarati prompts are drafts needing native-speaker review.

## Delivery

| Mode | What happens |
|---|---|
| **simulated** (default) | Every message is rendered and stored in `deliveries` with status "simulated"; nothing is sent |
| **twilio** | Sends via the Twilio REST API: SMS, WhatsApp (sandbox) and voice calls with inline TwiML. `POST /alerts/{id}/refresh-status` pulls delivery status back into the audit log |

**To enable Twilio**, set all of these:
- `HEAT_DISPATCH_MODE=twilio`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- `TWILIO_SMS_FROM`, `TWILIO_WHATSAPP_FROM` (sandbox number), `TWILIO_VOICE_FROM`
- `data/manual/test_recipients.csv` with **your own verified test numbers**. This file is git-ignored; the example file is refused in Twilio mode.
- optional `HEAT_PUBLIC_URL`, the public address of the API, for the voice keypad menu.

Recipients file columns: `name, phone, channel, lang, audience, ward_id`. Use `*` in `ward_id` for "the alert's highest-risk ward".

## Command dashboard

- **Status strip**, on every screen:
  - ward counts by level;
  - the active or forecast heatwave event;
  - the number of cooling deserts;
  - **alerts awaiting review** (click to open);
  - a clear **"Simulated delivery (nothing is sent)"** badge.
- **Plan tab** (Phase 6): city-wide measures, priority wards and resource allocation. It follows the role switch: Municipal ranks by mortality risk, Healthcare by hospitalization risk and ambulances.
- **Alerts tab:** the alert list and review screen. There you can:
  - toggle wards, audiences, languages and channels;
  - edit templates with a preview and character count;
  - approve with a note, or reject with a reason;
  - dispatch after a confirmation step;
  - open the CAP link and see the deliveries table and audit trail.

  The officer's name and the API token are remembered in the browser.
- `GET /dashboard` returns the whole command summary in one call.
- Links: `?tab=alerts`, `?alert=<id>`.

## Demo (replay)

```bash
python -m api.cli replay may2024
python -m api.cli alerts may2024      # 26 drafts for 7 May – 10 June 2024; nothing is sent
uvicorn api.main:app                  # open /?replay=may2024&tab=alerts
```

Tested end to end on a copy of the database:
- 26 drafts; running the engine again created none;
- dispatch before approval refused; approval without a name refused;
- an edit to the English SMS carried through to all wards;
- approved by "A. Officer", then editing and a second dispatch refused;
- 4 simulated deliveries (English and Gujarati SMS, Gujarati voice, a ward-specific volunteer);
- CAP marked *Exercise*; audit trail drafted → edited → approved → dispatched.

## Not done / limitations

- **No real phone has received a message yet.** The phase's exit criterion ("the test phone receives SMS and a voice call") needs a Twilio account, sandbox numbers and your own verified test phones. The adapter is written and follows Twilio's REST API, but hasn't been exercised against Twilio.
- **No user accounts.** The officer's name is typed in; the optional API token is shared. A real deployment needs per-user login.
- **Translations:** Hindi and Gujarati messages and voice prompts are drafts needing native-speaker review; the app says so wherever they appear.
- **Twilio Indian sender rules:** delivering to Indian numbers from a trial account may be restricted by DLT registration. The fallback is the dispatch log shown in the app.

## Sources

- OASIS Common Alerting Protocol 1.2: https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html (schema: `tests/data/CAP-v1.2.xsd`)
- Twilio TwiML `<Say>` and text-to-speech languages: https://www.twilio.com/docs/voice/twiml/say/text-speech
- WMO CAP training (urgency, severity, certainty): https://etrp.wmo.int/mod/book/view.php?id=11045&chapterid=1647
