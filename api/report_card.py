"""Post-event report card (Phase 9, proposal §9.5): one page per heatwave event.

For one event in a run (live forecast or replay) it gathers:
  - what the model predicted: Red / Orange+ ward-days, peak day, wards affected;
  - early warning: how many Red ward-days had P(Red) ≥ the trigger threshold in the forecasts
    issued 3-5 days before (replay) or in the ensemble (live);
  - checks against reference observations when a replay has them (IMD red-alert window and
    the Heat Action Plan colour from observed airport Tmax);
  - health-worker reports vs expected share, and anomaly flags;
  - what officers did: alerts approved / rejected / dispatched and deliveries, from the
    alerts table and the audit log.
Everything is rendered as a self-contained HTML page (print it to PDF from the browser, or
see scripts/demo_setup.py which also writes a PDF). Synthetic reports and simulated deliveries
are labelled as such wherever they appear.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from api import jobs, loop
from heatrisk import load_config

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ["green", "yellow", "orange", "red"]
COLOURS = {"green": "#3f9b5a", "yellow": "#e3b505", "orange": "#e8731c", "red": "#c62828"}
PAD_DAYS = 5          # days shown before and after the event


# ---------- data

def _scores(conn, run_id: int) -> pd.DataFrame:
    rows = [{"ward_id": r[0], "date": r[1], **{k: v for k, v in json.loads(r[2]).items() if not k.startswith("explanation")}}
            for r in conn.execute("SELECT ward_id, date, data FROM daily_scores WHERE run_id=?", (run_id,))]
    return pd.DataFrame(rows)


def _probs(conn, run_id: int | None) -> pd.DataFrame:
    if run_id is None:
        return pd.DataFrame(columns=["ward_id", "date", "p_red"])
    return pd.DataFrame([dict(r) for r in conn.execute(
        "SELECT ward_id, date, p_orange, p_red FROM ensemble_probs WHERE run_id=?", (run_id,))],
        columns=["ward_id", "date", "p_orange", "p_red"])


def events(conn, run_id: int) -> list[dict]:
    return [json.loads(r[0]) for r in conn.execute("SELECT event FROM events WHERE run_id=?", (run_id,))]


def _reference(replay: str | None) -> pd.DataFrame | None:
    spec = jobs.REPLAYS.get(replay or "", {})
    path = spec.get("reference")
    if not path or not (ROOT / path).exists():
        return None
    ref = pd.read_csv(ROOT / path, parse_dates=["date"])
    ref["date"] = ref["date"].dt.strftime("%Y-%m-%d")
    return ref[["date", "station_tmax", "hap_level", "imd_red"]]


def build(conn, run: dict, prob_run: dict | None, replay: str | None, event_index: int = 0) -> dict:
    cfg = load_config()
    evs = events(conn, run["run_id"])
    if not evs:
        raise LookupError("no heatwave event in this run")
    if not 0 <= event_index < len(evs):
        raise LookupError(f"event {event_index} not found (this run has {len(evs)})")
    ev = evs[event_index]
    sc = _scores(conn, run["run_id"])
    lo = (pd.Timestamp(ev["start"]) - pd.Timedelta(days=PAD_DAYS)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(ev["end"]) + pd.Timedelta(days=PAD_DAYS)).strftime("%Y-%m-%d")
    win = sc[(sc["date"] >= lo) & (sc["date"] <= hi)].copy()
    in_ev = win[(win["date"] >= ev["start"]) & (win["date"] <= ev["end"])]
    names = dict(conn.execute("SELECT ward_id, ward_name FROM wards").fetchall())
    win["lvl"] = win["alert_mri"].map(LEVELS.index)
    in_ev = in_ev.assign(lvl=in_ev["alert_mri"].map(LEVELS.index))

    # early warning from probabilities
    trig = next((t for t in cfg["ensemble"].get("triggers", []) if t["when"] == "p_red"), {"at_least": 0.4})
    thr = float(trig["at_least"])
    pr = _probs(conn, prob_run["run_id"] if prob_run else None)
    red = in_ev[in_ev["lvl"] == 3][["ward_id", "date"]].merge(pr, on=["ward_id", "date"], how="left")
    warned = int((red["p_red"] >= thr).sum())
    with_prob = int(red["p_red"].notna().sum())
    first_red = in_ev.loc[in_ev["lvl"] == 3, "date"].min() if (in_ev["lvl"] == 3).any() else None
    early = None
    if first_red is not None and len(pr):
        p_win = pr[(pr["date"] >= lo) & (pr["p_red"] >= thr)]
        if len(p_win):
            early = p_win["date"].min()

    # day series (city)
    day = win.groupby("date").agg(n_red=("lvl", lambda s: int((s == 3).sum())),
                                  n_green=("lvl", lambda s: int((s == 0).sum())),
                                  n_orange=("lvl", lambda s: int((s == 2).sum())),
                                  n_yellow=("lvl", lambda s: int((s == 1).sum())),
                                  median_mri=("mri", "median"), tmax=("tmax", "median")).reset_index()
    bands = cfg["alerts"]["levels"]
    day["median_level"] = [next(k for k, v in bands.items() if m <= v) for m in day["median_mri"]]

    # reference checks
    ref = _reference(replay)
    verification = None
    if ref is not None:
        v = day.merge(ref, on="date", how="left")
        day = v
        ok = v.dropna(subset=["hap_level"])
        r_i, m_i = ok["hap_level"].map(LEVELS.index), ok["median_level"].map(LEVELS.index)
        imd = v[v["imd_red"] == True]  # noqa: E712
        lead, d = 0, None
        if len(imd):
            d = pd.Timestamp(imd["date"].min()) - pd.Timedelta(days=1)
            vv = v.set_index("date")
            while d.strftime("%Y-%m-%d") in vv.index and (vv.loc[d.strftime("%Y-%m-%d"), ["n_red", "n_orange"]].sum() > 0):
                lead += 1
                d -= pd.Timedelta(days=1)
        verification = {
            "days": int(len(ok)),
            "hits": int(((r_i >= 2) & (m_i >= 2)).sum()), "plan_warn_days": int((r_i >= 2).sum()),
            "missed": int(((r_i >= 2) & (m_i < 2)).sum()),
            "false": int(((r_i <= 1) & (m_i >= 2)).sum()), "plan_quiet_days": int((r_i <= 1).sum()),
            "same_level": int((r_i == m_i).sum()),
            "imd_days": int(len(imd)), "imd_days_any_red": int((imd["n_red"] > 0).sum()),
            "imd_lead_days": lead if len(imd) else None,
            "imd_window": [imd["date"].min(), imd["date"].max()] if len(imd) else None,
            "note": jobs.REPLAYS[replay].get("reference_note", ""),
        }

    # health-worker reports
    c = loop.counts(conn, replay)
    c = c[(c["date"] >= lo) & (c["date"] <= hi)] if len(c) else c
    s = loop.scores(conn, run["run_id"])
    from heatrisk import feedback
    flags = feedback.flags(c[["ward_id", "date", "reports"]], s, cfg) if len(c) else pd.DataFrame()
    exp_rows = []
    for d_, g in (c.groupby("date") if len(c) else []):
        e = feedback.expected(g.set_index("ward_id")["reports"], s[s["date"] == d_])
        exp_rows += [{"ward_id": w, "date": d_, "expected": float(x)} for w, x in e.items()]
    exp = pd.DataFrame(exp_rows, columns=["ward_id", "date", "expected"])
    rep_by_ward = c.groupby("ward_id")["reports"].sum() if len(c) else pd.Series(dtype=float)
    exp_by_ward = exp.groupby("ward_id")["expected"].sum() if len(exp) else pd.Series(dtype=float)
    reports = {"total": int(c["reports"].sum()) if len(c) else 0,
               "synthetic": bool(len(c) and c["synthetic"].max()),
               "by_day": c.groupby("date")["reports"].sum().astype(int).to_dict() if len(c) else {},
               "flags": [{"ward_id": f.ward_id, "ward_name": names[f.ward_id], "date": f.date, "reports": int(f.reports),
                          "expected": round(float(f.expected), 2), "ratio": round(float(f.ratio), 1),
                          "mri": round(float(in_ev.set_index(["ward_id", "date"])["mri"].get((f.ward_id, f.date), float("nan"))), 1)}
                         for f in flags.itertuples()] if len(flags) else []}

    # alerts and officer actions
    mode = "replay" if replay else "live"
    al = [dict(r) for r in conn.execute(
        "SELECT alert_id, date, level, kind, wards, status, decided_by, decided_at, decision_note, dispatched_at "
        "FROM alerts WHERE mode=? AND IFNULL(replay,'')=? AND date BETWEEN ? AND ? ORDER BY date, alert_id",
        (mode, replay or "", lo, hi))]
    for a in al:
        a["wards"] = json.loads(a["wards"])
    status_n = pd.Series([a["status"] for a in al]).value_counts().to_dict() if al else {}
    covered = {(w, a["date"]) for a in al if a["status"] in ("approved", "dispatched") and a["level"] == "red" for w in a["wards"]}
    red_keys = set(map(tuple, in_ev.loc[in_ev["lvl"] == 3, ["ward_id", "date"]].to_numpy()))
    ids = [a["alert_id"] for a in al]
    deliveries = {}
    if ids:
        q = f"SELECT channel, status, provider, COUNT(*) FROM deliveries WHERE alert_id IN ({','.join('?' * len(ids))}) GROUP BY 1,2,3"
        for ch, st, prov, n in conn.execute(q, ids):
            deliveries.setdefault(ch, {})[f"{st}"] = deliveries.get(ch, {}).get(st, 0) + n
    actions = []
    if ids:
        for r in conn.execute("SELECT at, actor, action, detail FROM audit_log WHERE action IN "
                              "('alert_approved','alert_rejected','alert_dispatched','alert_edited') ORDER BY id"):
            det = json.loads(r[3]) if r[3] else {}
            if det.get("alert_id") in ids:
                a = next(x for x in al if x["alert_id"] == det["alert_id"])
                actions.append({"at": r[0], "officer": r[1], "action": r[2].replace("alert_", ""), "alert_id": det["alert_id"],
                                "day": a["date"], "level": a["level"], "wards": len(a["wards"]),
                                "detail": det.get("note") or det.get("reason") or
                                          (f"{det.get('messages')} messages ({det.get('mode')})" if "messages" in det else "")})

    # wards
    g = in_ev.groupby("ward_id")
    wt = pd.DataFrame({"peak_mri": g["mri"].max(), "red_days": g["lvl"].apply(lambda s: int((s == 3).sum())),
                       "orange_plus_days": g["lvl"].apply(lambda s: int((s >= 2).sum())),
                       "first_red": in_ev[in_ev["lvl"] == 3].groupby("ward_id")["date"].min(),
                       "pvi": g["pvi"].first()})
    wt["reports"] = rep_by_ward.reindex(wt.index).fillna(0).astype(int)
    wt["expected"] = exp_by_ward.reindex(wt.index).fillna(0).round(1)
    wt["flagged"] = wt.index.isin({f["ward_id"] for f in reports["flags"]})
    wt["red_days_alerted"] = [sum((w, d) in covered for d in in_ev.loc[(in_ev["ward_id"] == w) & (in_ev["lvl"] == 3), "date"])
                              for w in wt.index]
    wt["ward_name"] = [names[w] for w in wt.index]
    wt = wt.reset_index().sort_values(["red_days", "peak_mri"], ascending=False)

    return {
        "title": jobs.REPLAYS[replay]["title"] if replay else "Live forecast",
        "mode": mode, "replay": replay, "event": {k: ev[k] for k in ("start", "peak", "end", "days")},
        "event_index": event_index, "n_events": len(evs), "window": [lo, hi],
        "n_wards": int(sc["ward_id"].nunique()),
        "summary": {"red_ward_days": int((in_ev["lvl"] == 3).sum()), "orange_plus_ward_days": int((in_ev["lvl"] >= 2).sum()),
                    "wards_red": int(in_ev.loc[in_ev["lvl"] == 3, "ward_id"].nunique()),
                    "peak_median_mri": ev.get("peak_median_mri"), "first_red": first_red,
                    "red_warned": warned, "red_with_prob": with_prob, "threshold": thr, "first_p_red_day": early,
                    "prob_source": (prob_run or {}).get("source") or "",
                    "red_ward_days_alerted": len(covered & red_keys)},
        "days": day.where(day.notna(), None).to_dict("records"),
        "verification": verification, "reports": reports,
        "alerts": {"total": len(al), "by_status": status_n, "deliveries": deliveries, "actions": actions,
                   "simulated": any(("simulated" in (x["detail"] or "")) for x in actions) or
                                any("simulated" in d for d in deliveries.values())},
        "wards": wt.where(wt.notna(), None).to_dict("records"),
        "limitations": [
            "Model estimates, not clinical predictions. Health outcomes for this event are known only city-wide.",
            "Early warning in a replay uses archived deterministic forecasts from three models (9 members), not the live 122-member ensemble.",
            "Sheet-roof shares are census-based estimates; elderly, children and outdoor-worker indicators are held at the city midpoint.",
        ] + (["Report flags are prompts to verify, not confirmed clusters: at p < 0.01 over hundreds of ward-days, "
              "about one flag can occur by chance."] if reports["flags"] else [])
          + (["Health-worker reports in this card are SYNTHETIC demo data."] if reports["synthetic"] else [])
          + (["Alert deliveries were SIMULATED: nothing was sent to real phones."] if deliveries and all(
              set(v) <= {"simulated"} for v in deliveries.values()) else []),
    }


# ---------- HTML

def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _d(s: str | None) -> str:
    return pd.Timestamp(s).strftime("%d %b") if s else "—"


def _timeline_svg(days: list[dict], reports: dict, n_wards: int, ev: dict) -> str:
    w, h, top, bot, left = 720, 170, 12, 34, 30
    n = len(days)
    bw = (w - left - 8) / max(n, 1)
    ph = h - top - bot
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Wards at each alert level per day" class="tl">']
    for i, d in enumerate(days):
        x = left + i * bw
        if d.get("imd_red"):
            out.append(f'<rect x="{x:.1f}" y="{top}" width="{bw:.1f}" height="{ph}" fill="#c62828" opacity="0.10"/>')
        if ev["start"] <= d["date"] <= ev["end"]:
            out.append(f'<rect x="{x:.1f}" y="{h - bot + 2}" width="{bw:.1f}" height="4" fill="#555"/>')
        y = top + ph
        for key, col in (("n_green", "#cfe8d4"), ("n_yellow", COLOURS["yellow"]), ("n_orange", COLOURS["orange"]), ("n_red", COLOURS["red"])):
            hh = ph * d[key] / n_wards
            y -= hh
            if hh > 0:
                out.append(f'<rect x="{x + 1:.1f}" y="{y:.1f}" width="{bw - 2:.1f}" height="{hh:.1f}" fill="{col}"/>')
        if d.get("hap_level"):
            out.append(f'<circle cx="{x + bw / 2:.1f}" cy="{top + ph + 14}" r="3.5" fill="{COLOURS[d["hap_level"]]}" stroke="#333" stroke-width="0.5"/>')
        if i % 3 == 0 or d["date"] == ev["peak"]:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 4}" text-anchor="middle" class="ax">{_d(d["date"])}</text>')
    rmax = max(reports["by_day"].values(), default=0)
    if rmax:
        pts = " ".join(f"{left + i * bw + bw / 2:.1f},{top + ph - ph * 0.9 * reports['by_day'].get(d['date'], 0) / rmax:.1f}"
                       for i, d in enumerate(days))
        out.append(f'<polyline points="{pts}" fill="none" stroke="#1f4e9c" stroke-width="1.6"/>')
    for frac in (0, 0.5, 1):
        y = top + ph * (1 - frac)
        out.append(f'<text x="{left - 4}" y="{y + 3:.1f}" text-anchor="end" class="ax">{int(n_wards * frac)}</text>')
    out.append("</svg>")
    return "".join(out)


CSS = """
:root{--ink:#1d1d1f;--muted:#5b5b60;--line:#dcdce0;--bg:#fff;--soft:#f5f5f7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.page{max-width:820px;margin:0 auto;padding:22px 20px}
h1{font-size:20px;margin:0}h2{font-size:14px;margin:18px 0 6px;border-bottom:1px solid var(--line);padding-bottom:3px}
.sub{color:var(--muted);margin:2px 0 10px}.tag{display:inline-block;border:1px solid #b00020;color:#b00020;border-radius:3px;padding:0 5px;font-size:11px;margin-left:6px}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.kpi{background:var(--soft);border-radius:6px;padding:8px}
.kpi b{display:block;font-size:19px}.kpi span{color:var(--muted);font-size:11.5px}
table{border-collapse:collapse;width:100%;font-size:12px}th,td{border-bottom:1px solid var(--line);padding:3px 5px;text-align:left}
th{color:var(--muted);font-weight:600}td.n,th.n{text-align:right}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px;vertical-align:-1px}
.two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}.tl{width:100%;height:auto}.ax{font-size:9px;fill:var(--muted)}
.legend{font-size:11px;color:var(--muted)}.legend i{display:inline-block;width:10px;height:10px;margin:0 3px 0 10px;vertical-align:-1px}
ul{margin:4px 0;padding-left:18px}.muted{color:var(--muted)}.flag{color:#b00020;font-weight:600}
.appendix{page-break-before:always}
@media (max-width:600px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.two{grid-template-columns:minmax(0,1fr)}.page{padding:16px}}
@media print{.page{padding:0;max-width:none}body{font-size:11px}}
"""


def render_html(r: dict) -> str:
    s, ev, v, rep, al = r["summary"], r["event"], r["verification"], r["reports"], r["alerts"]
    tags = "".join(f'<span class="tag">{t}</span>' for t, on in (
        ("REPLAY", r["mode"] == "replay"), ("SYNTHETIC REPORTS", rep["synthetic"]), ("SIMULATED DELIVERY", al["simulated"])) if on)
    p = []
    p.append(f'<h1>Heatwave report card — {_e(r["title"])}{tags}</h1>')
    p.append(f'<p class="sub">Ahmedabad, {r["n_wards"]} wards · event {_d(ev["start"])} – {_d(ev["end"])} {pd.Timestamp(ev["end"]).year} '
             f'({ev["days"]} days, peak {_d(ev["peak"])}) · model estimates, not clinical predictions'
             + (f' · event {r["event_index"] + 1} of {r["n_events"]}' if r["n_events"] > 1 else "") + "</p>")
    warned = f'{s["red_warned"]} of {s["red_with_prob"]}' if s["red_with_prob"] else "n/a"
    p.append('<div class="kpis">'
             f'<div class="kpi"><b>{s["wards_red"]} / {r["n_wards"]}</b><span>wards reached Red (mortality risk)</span></div>'
             f'<div class="kpi"><b>{s["red_ward_days"]}</b><span>Red ward-days · {s["orange_plus_ward_days"]} Orange-or-worse</span></div>'
             f'<div class="kpi"><b>{warned}</b><span>Red ward-days with P(Red) ≥ {s["threshold"]:.0%} in forecasts 3–5 days ahead</span></div>'
             f'<div class="kpi"><b>{s["red_ward_days_alerted"]} / {s["red_ward_days"]}</b><span>Red ward-days covered by an approved Red alert</span></div>'
             '</div>')

    p.append("<h2>What happened, day by day</h2>")
    p.append(_timeline_svg(r["days"], rep, r["n_wards"], ev))
    p.append('<div class="legend">Wards at<i style="background:#cfe8d4"></i>Green<i style="background:#e3b505"></i>Yellow<i style="background:#e8731c"></i>Orange'
             '<i style="background:#c62828"></i>Red' + ('<i style="background:#c62828;opacity:.15"></i>IMD red alert' if v else "")
             + (' · dots: Heat Action Plan colour from observed airport Tmax' if v else "")
             + (' · <span style="color:#1f4e9c">line: health-worker reports</span>' if rep["total"] else "")
             + ' · grey bar: event days</div>')

    p.append('<div class="two"><div>')
    p.append("<h2>Checks against observations</h2>")
    if v:
        p.append("<table>"
                 f'<tr><td>IMD red-alert days ({_d(v["imd_window"][0])}–{_d(v["imd_window"][1])}) with a ward at Red</td><td class="n">{v["imd_days_any_red"]} of {v["imd_days"]}</td></tr>'
                 f'<tr><td>Days of Orange-or-worse warning before IMD\'s red alert</td><td class="n">{v["imd_lead_days"]}</td></tr>'
                 f'<tr><td>Plan Orange/Red days (observed Tmax) the model also rated Orange+ (median ward)</td><td class="n">{v["hits"]} of {v["plan_warn_days"]}</td></tr>'
                 f'<tr><td>Missed: plan Orange/Red, model below</td><td class="n">{v["missed"]}</td></tr>'
                 f'<tr><td>Over-warning: model Orange+, plan Yellow or none</td><td class="n">{v["false"]} of {v["plan_quiet_days"]}</td></tr>'
                 f'<tr><td>Same level as the plan</td><td class="n">{v["same_level"]} of {v["days"]} days</td></tr>'
                 "</table>")
        p.append(f'<p class="muted">{_e(v["note"])}</p>')
    else:
        p.append('<p class="muted">No reference observations are attached to this run yet. Enter observed Tmax / IMD warnings after the event to fill this section.</p>')
    p.append("<h2>Health-worker reports</h2>")
    if rep["total"]:
        p.append(f'<p>{rep["total"]} reports in the window{" (synthetic demo data)" if rep["synthetic"] else ""}. '
                 f'{len(rep["flags"])} ward-day{"s" if len(rep["flags"]) != 1 else ""} flagged for more cases than the model\'s share.</p>')
        if rep["flags"]:
            p.append('<table><tr><th>Ward</th><th>Day</th><th class="n">Reports</th><th class="n">Expected</th><th class="n">MRI</th></tr>'
                     + "".join(f'<tr><td class="flag">{_e(f["ward_name"])}</td><td>{_d(f["date"])}</td><td class="n">{f["reports"]}</td>'
                               f'<td class="n">{f["expected"]}</td><td class="n">{f["mri"]}</td></tr>' for f in rep["flags"]) + "</table>")
    else:
        p.append('<p class="muted">No health-worker reports were received for this event.</p>')
    p.append("</div><div>")
    p.append("<h2>Alerts and actions</h2>")
    st = al["by_status"]
    p.append(f'<p>{al["total"]} alert drafts: ' + ", ".join(f"{n} {k}" for k, n in sorted(st.items())) + ".</p>" if al["total"]
             else '<p class="muted">No alerts were drafted.</p>')
    if al["deliveries"]:
        p.append("<p>Messages: " + "; ".join(f"{ch} " + ", ".join(f"{n} {k}" for k, n in d.items()) for ch, d in al["deliveries"].items()) + ".</p>")
    if al["actions"]:
        acts = pd.DataFrame(al["actions"])
        grp = acts.groupby(["level", "action", "officer"]).agg(alerts=("alert_id", "nunique"), first=("day", "min"),
                                                                 last=("day", "max")).reset_index()
        grp["o"] = grp["level"].map(LEVELS.index)
        p.append('<table><tr><th>Level</th><th>Action</th><th class="n">Alerts</th><th>Days</th><th>Officer</th></tr>'
                 + "".join(f'<tr><td><span class="dot" style="background:{COLOURS[g.level]}"></span>{g.level.title()}</td><td>{_e(g.action)}</td>'
                           f'<td class="n">{g.alerts}</td><td>{_d(g.first)}–{_d(g.last)}</td><td>{_e(g.officer)}</td></tr>'
                           for g in grp.sort_values(["o", "action"], ascending=[False, True]).itertuples()) + "</table>")
        notes = [a for a in al["actions"] if a["action"] in ("rejected", "edited")]
        if notes:
            p.append("<ul>" + "".join(f'<li>{_d(a["day"])} {a["level"]}: {a["action"]} by {_e(a["officer"])} — {_e(a["detail"])}</li>'
                                      for a in notes[:5]) + "</ul>")
        p.append('<p class="muted">Every decision is in the audit log with officer name and time.</p>')
    elif al["total"]:
        p.append('<p class="muted">No officer decisions recorded yet: drafts are awaiting review.</p>')
    p.append("<h2>Most affected wards</h2>")
    top = r["wards"][:10]
    p.append('<table><tr><th>Ward</th><th class="n">Red days</th><th class="n">Peak MRI</th><th class="n">Reports / exp.</th></tr>'
             + "".join(f'<tr><td{" class=flag" if w["flagged"] else ""}>{_e(w["ward_name"])}</td><td class="n">{w["red_days"]}</td>'
                       f'<td class="n">{w["peak_mri"]:.0f}</td><td class="n">{w["reports"]} / {w["expected"]}</td></tr>' for w in top) + "</table>")
    p.append("</div></div>")
    p.append("<h2>Limitations</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in r["limitations"]) + "</ul>")

    # appendix: all wards
    p.append('<div class="appendix"><h2>Appendix — all wards</h2>')
    p.append('<table><tr><th>Ward</th><th class="n">Red days</th><th class="n">Orange+ days</th><th>First Red</th>'
             '<th class="n">Red days alerted</th><th class="n">Peak MRI</th><th class="n">PVI</th><th class="n">Reports</th><th class="n">Expected</th></tr>'
             + "".join(f'<tr><td{" class=flag" if w["flagged"] else ""}>{_e(w["ward_name"])}</td><td class="n">{w["red_days"]}</td>'
                       f'<td class="n">{w["orange_plus_days"]}</td><td>{_d(w["first_red"])}</td><td class="n">{w["red_days_alerted"]}</td>'
                       f'<td class="n">{w["peak_mri"]:.0f}</td><td class="n">{w["pvi"]:.0f}</td><td class="n">{w["reports"]}</td>'
                       f'<td class="n">{w["expected"]}</td></tr>' for w in r["wards"]) + "</table>")
    p.append(f'<p class="muted">Early-warning source: {_e(s["prob_source"])}</p></div>')
    body = "\n".join(p)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Heatwave Report Card</title><style>{CSS}</style></head><body><main class="page">{body}</main></body></html>')
