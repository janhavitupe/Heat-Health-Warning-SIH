# Phase 7 — Command Dashboard & Alert Delivery

**Effort:** M · **MVP:** ✅ · **Depends on:** Phases 5, 6 · **Unblocks:** Phase 8 · **Status:** ✅ complete in simulated mode ([write-up](../docs/alerts_phase7.md)); real Twilio delivery needs your credentials and test phones

## Goal
Give authorities one screen to see the city's status and act on it, with a human-in-the-loop workflow that takes an alert from automatic trigger to reviewed, approved, and dispatched — by SMS, WhatsApp, and voice.

## Tasks

### City-wide command dashboard (§5)
- [x] Header: city status, active/forecast heatwave event, last data refresh. *Status strip + `/dashboard`.*
- [x] Priority-ward list with alert level, probability, top driver, and recommended actions.
- [x] Panels: safe work windows today (*Innovation 4*), cooling deserts and recommended sites (*Innovation 5*), resource allocation plan.
- [x] Role-specific views: Municipal (MRI, cooling, work hours, public warnings) and Healthcare (HRI, hospital alerts, ambulance readiness).

### Alert workflow (§6.6, §11.3)
- [x] Alert Engine: when a ward crosses a level (or a probability trigger fires), create a draft alert with ward, level, drivers, actions, and pre-filled advisories. *One draft per day and level; no duplicates; supersede/update logic.*
- [x] Review screen: officer can edit text, change target wards/audiences, approve, or reject with a reason.
- [x] Audit log: every draft, edit, approval, rejection, and dispatch recorded with user and timestamp.
- [x] Generate CAP-compliant XML for each approved alert (for future NDMA Sachet integration). *Validated against the OASIS CAP 1.2 XSD in tests.*

### Delivery (simulated)
- [x] Twilio SMS and WhatsApp sandbox dispatch to a test recipient list per ward and audience. *Adapter written; simulated by default; **not yet run against Twilio** (needs your account and verified test numbers).*
- [x] **IVR voice alerts**: Twilio Programmable Voice with recorded or TTS messages in local languages; caller can press a key to repeat or hear nearest cooling point. *TwiML with Google en-IN/hi-IN/gu-IN voices; 1 = repeat, 2 = cooling places.*
- [x] Delivery status tracked back into the audit log. *`refresh-status` polls Twilio; simulated deliveries recorded as such.*

## Deliverables
- Command dashboard (both roles)
- Alert review/approval UI and audit log
- CAP XML export
- Working sandbox SMS, WhatsApp, and voice dispatch

## Exit criteria
- In replay mode, an alert flows trigger → review → approval → dispatch, and the test phone receives SMS and a voice call.
- Nothing is sent without explicit human approval.

## Risks & fallbacks
| Risk | Fallback |
|---|---|
| Twilio sandbox limits on Indian numbers | Demo with verified test numbers; show dispatch log if delivery is restricted. |
| Voice TTS quality in regional language | Use pre-recorded human voice clips for core messages. |
