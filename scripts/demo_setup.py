"""Prepare the demo database and the May 2024 report card (Phase 9).

Copies the main API database to data/api/demo.db (so the working database is untouched),
then, for the May 2024 replay:
  1. clears earlier alerts, deliveries, reports and audit entries of that replay;
  2. drafts alerts for every Orange/Red ward-day;
  3. seeds the 69 labelled synthetic health-worker reports (with the Vatva cluster);
  4. plays a scripted officer, "Demo officer (simulated)", who approves and dispatches every
     Red and Orange draft during the heatwave event, except the first Red alert (LIVE_DAY),
     which is left as a draft for the presenter to approve on stage. SIMULATED dispatch only.
  5. writes the report card to docs/report_card_may2024.html and .pdf (PDF via headless Chrome).

Run the demo app on this database afterwards:
  HEAT_DB=data/api/demo.db uvicorn api.main:app --port 8000
Usage:  python scripts/demo_setup.py [--no-pdf]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SRC, DEMO = ROOT / "data" / "api" / "heat.db", ROOT / "data" / "api" / "demo.db"
REPLAY = "may2024"
OFFICER = "Demo officer (simulated)"
LIVE_DAY = "2024-05-17"          # first Red day: left as a draft for the live approval
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium",
          "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def main() -> None:
    if os.environ.get("HEAT_DISPATCH_MODE") == "twilio":
        raise SystemExit("demo_setup only runs in simulated dispatch mode: unset HEAT_DISPATCH_MODE")
    if not SRC.exists():
        raise SystemExit("data/api/heat.db not found: run `python -m api.cli all` first")
    shutil.copyfile(SRC, DEMO)
    os.environ["HEAT_DB"] = str(DEMO)

    from api import alerts, db, dispatch, loop, report_card
    from api.main import _runs, generate_drafts

    with db.connect(DEMO) as conn:
        ids = [r[0] for r in conn.execute("SELECT alert_id FROM alerts WHERE mode='replay' AND replay=?", (REPLAY,))]
        if ids:
            q = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM deliveries WHERE alert_id IN ({q})", ids)
        conn.execute("DELETE FROM alerts WHERE mode='replay' AND replay=?", (REPLAY,))
        conn.execute("DELETE FROM report_counts WHERE mode='replay' AND replay=?", (REPLAY,))
        conn.execute("DELETE FROM audit_log WHERE action LIKE 'alert_%' OR action LIKE 'synthetic_%'")
        run, prob_run = _runs(conn, REPLAY)
        drafted = generate_drafts(conn, REPLAY)
        seeded = loop.seed_synthetic(conn, run["run_id"], REPLAY)
        ev = report_card.events(conn, run["run_id"])[0]
        done = 0
        for a in conn.execute("SELECT alert_id FROM alerts WHERE mode='replay' AND replay=? AND status='draft' "
                              "AND level IN ('orange','red') AND date BETWEEN ? AND ? ORDER BY date, alert_id",
                              (REPLAY, ev["start"], ev["end"])).fetchall():
            if alerts.load(conn, a[0])["level"] == "red" and alerts.load(conn, a[0])["date"] == LIVE_DAY:
                continue
            alerts.approve(conn, a[0], OFFICER, "Scripted demo approval")
            dispatch.dispatch(conn, a[0], OFFICER)
            done += 1
        card = report_card.build(conn, run, prob_run, REPLAY, 0)
    print(f"demo.db: {len(drafted)} drafts, {seeded} synthetic reports, {done} alerts approved and dispatched (simulated); "
          f"Red alert for {LIVE_DAY} left as a draft for the live demo")

    out = ROOT / "docs" / "report_card_may2024.html"
    out.write_text(report_card.render_html(card), encoding="utf-8")
    print("wrote", out.relative_to(ROOT))
    if "--no-pdf" in sys.argv:
        return
    chrome = next((c for c in CHROME if Path(c).exists()), None)
    if chrome is None:
        print("Chrome not found: open the HTML file and print it to PDF instead")
        return
    pdf = out.with_suffix(".pdf")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", out.as_uri()], check=True, capture_output=True, timeout=120)
    print("wrote", pdf.relative_to(ROOT))


if __name__ == "__main__":
    main()
