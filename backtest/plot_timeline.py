"""Timeline chart of the May 2024 backtest as a self-contained SVG (no plotting dependency).

Top: median-ward MRI (line) and the range across all 48 wards (band) against the
alert bands, with the IMD red-alert window marked. Bottom: two strips comparing,
day by day, the Heat Action Plan level from observed airport Tmax with the model
level for the median ward. Every day has a hover tooltip.

Reads backtest/results/may2024_city.csv (from backtest/may2024.py).
Writes backtest/results/may2024_timeline.svg
Usage:  python backtest/plot_timeline.py
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd

RESULTS = Path(__file__).resolve().parent / "results"
LEVELS = ["green", "yellow", "orange", "red"]
LABELS = {"green": "Green", "yellow": "Yellow", "orange": "Orange", "red": "Red"}
BANDS = [(0, 40, "green"), (40, 60, "yellow"), (60, 80, "orange"), (80, 100, "red")]

W, H = 960, 536
L, R, T = 64, 128, 72           # plot margins (right margin holds band labels)
PH = 280                        # plot height
STRIP_Y = T + PH + 64           # first comparison strip
STRIP_H = 22

STYLE = """
svg { --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7;
      --series:#2a78d6; --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
      --window:rgba(11,11,11,0.06); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
@media (prefers-color-scheme: dark) {
  svg { --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835;
        --series:#3987e5; --window:rgba(255,255,255,0.07); }
}
.bg { fill: var(--surface); }
.t1 { fill: var(--ink); font-size: 16px; font-weight: 600; }
.t2 { fill: var(--ink2); font-size: 12px; }
.tm { fill: var(--muted); font-size: 11px; }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis { stroke: var(--axis); stroke-width: 1; }
.band { opacity: 0.10; }
.green { fill: var(--good); } .yellow { fill: var(--warning); } .orange { fill: var(--serious); } .red { fill: var(--critical); }
.window { fill: var(--window); }
.range { fill: var(--series); opacity: 0.14; }
.line { fill: none; stroke: var(--series); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.dot { fill: var(--series); stroke: var(--surface); stroke-width: 2; }
.cell { stroke: var(--surface); stroke-width: 2; }
.hit { fill: transparent; }
.hit:hover { fill: rgba(127,127,127,0.10); }
"""


def main() -> None:
    city = pd.read_csv(RESULTS / "may2024_city.csv", parse_dates=["date"])
    n = len(city)
    step = (W - L - R) / n

    def x(i: float) -> float:
        return L + (i + 0.5) * step

    def y(v: float) -> float:
        return T + PH * (1 - v / 100)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'role="img" aria-labelledby="title desc">',
           "<title id=\"title\">May 2024 backtest: modelled heat-health risk vs official alerts</title>",
           "<desc id=\"desc\">Median-ward mortality risk index (MRI) per day, 1 May to 15 June 2024, with the range "
           "across 48 Ahmedabad wards, the IMD red-alert window of 20–24 May, and a day-by-day comparison with the "
           "Heat Action Plan level from observed airport maximum temperature.</desc>",
           f"<style>{STYLE}</style>",
           f'<rect class="bg" width="{W}" height="{H}"/>',
           f'<text class="t1" x="{L}" y="26">Model vs official alerts — Ahmedabad, May–June 2024</text>',
           f'<text class="t2" x="{L}" y="44">Mortality risk index (MRI), 48 wards. '
           'Line: median ward. Band: lowest to highest ward.</text>']

    # alert bands with labels (text labels carry the meaning, colour only supports it)
    for lo, hi, lvl in BANDS:
        out.append(f'<rect class="band {lvl}" x="{L}" y="{y(hi):.1f}" width="{W - L - R}" height="{y(lo) - y(hi):.1f}"/>')
        out.append(f'<text class="t2" x="{W - R + 10}" y="{(y(lo) + y(hi)) / 2 + 4:.1f}">{LABELS[lvl]} '
                   f'<tspan class="tm">{"≤" if lo == 0 else ">"}{lo if lo else hi}</tspan></text>')

    # IMD red-alert window
    imd = city.index[city["imd_red"]].tolist()
    if imd:
        x0, x1 = L + imd[0] * step, L + (imd[-1] + 1) * step
        out.append(f'<rect class="window" x="{x0:.1f}" y="{T}" width="{x1 - x0:.1f}" height="{PH}"/>')
        out.append(f'<text class="t2" x="{(x0 + x1) / 2:.1f}" y="{T - 6}" text-anchor="middle">IMD red alert 20–24 May</text>')

    # grid + y axis
    for v in (0, 20, 40, 60, 80, 100):
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        out.append(f'<text class="tm" x="{L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')
    out.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')

    # ward range band and median line
    top = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(city["mri_max"]))
    bot = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in reversed(list(enumerate(city["mri_min"]))))
    out.append(f'<polygon class="range" points="{top} {bot}"/>')
    out.append('<polyline class="line" points="' +
               " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(city["model_typical"])) + '"/>')
    peak = int(city["model_typical"].idxmax())
    pv = city.loc[peak]
    out.append(f'<circle class="dot" cx="{x(peak):.1f}" cy="{y(pv.model_typical):.1f}" r="4.5"/>')
    out.append(f'<text class="t2" x="{x(peak) + 8:.1f}" y="{y(pv.model_typical) - 8:.1f}">'
               f'Peak {pv.model_typical:.0f} on {pv.date:%d %b} (airport {pv.station_tmax:.1f} °C)</text>')

    # x axis labels: every 5th day, plus the first
    for i, d in enumerate(city["date"]):
        if i % 5 == 0:
            out.append(f'<text class="tm" x="{x(i):.1f}" y="{y(0) + 16:.1f}" text-anchor="middle">{d:%d %b}</text>')

    # comparison strips
    strips = [("Heat Action Plan (airport Tmax)", "hap_level"), ("Model (median ward)", "model_typical_level")]
    for k, (name, col) in enumerate(strips):
        sy = STRIP_Y + k * (STRIP_H + 10)
        out.append(f'<text class="t2" x="{L - 8}" y="{sy + 15}" text-anchor="end" font-size="11">'
                   f'{"Plan" if k == 0 else "Model"}</text>')
        for i, lvl in enumerate(city[col]):
            if isinstance(lvl, str):
                out.append(f'<rect class="cell {lvl}" x="{L + i * step:.1f}" y="{sy}" width="{step:.1f}" '
                           f'height="{STRIP_H}" rx="3"/>')
    out.append(f'<text class="tm" x="{L}" y="{STRIP_Y - 10}">Daily level: top row = Heat Action Plan rule on observed '
               'airport Tmax; bottom row = model, median ward.</text>')

    # legend
    ly = H - 22
    out.append(f'<line class="line" x1="{L}" x2="{L + 22}" y1="{ly}" y2="{ly}"/>'
               f'<text class="t2" x="{L + 28}" y="{ly + 4}">Median ward MRI</text>'
               f'<rect class="range" x="{L + 150}" y="{ly - 7}" width="22" height="14" rx="3"/>'
               f'<text class="t2" x="{L + 178}" y="{ly + 4}">Range across 48 wards</text>'
               f'<rect class="window" x="{L + 340}" y="{ly - 7}" width="22" height="14" rx="3"/>'
               f'<text class="t2" x="{L + 368}" y="{ly + 4}">IMD red-alert window</text>')

    # hover targets: one full-height column per day
    for i, r in city.iterrows():
        tip = (f"{r.date:%a %d %b %Y}\nMedian ward MRI {r.model_typical:.0f} ({LABELS[r.model_typical_level]})\n"
               f"Wards: {r.mri_min:.0f}–{r.mri_max:.0f}, {int(r.n_red)} at Red, {int(r.n_orange_plus)} at Orange+\n"
               f"Airport Tmax {r.station_tmax:.1f} °C → plan level {LABELS.get(r.hap_level, 'n/a')}"
               + ("\nIMD red alert day" if r.imd_red else ""))
        out.append(f'<rect class="hit" x="{L + i * step:.1f}" y="{T}" width="{step:.1f}" '
                   f'height="{STRIP_Y + 2 * STRIP_H + 10 - T}"><title>{escape(tip)}</title></rect>')

    out.append("</svg>")
    dest = RESULTS / "may2024_timeline.svg"
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
