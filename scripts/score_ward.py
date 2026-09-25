"""Score one ward and print the explained result.

Usage:
  python scripts/score_ward.py AMC-29                       # live forecast (past 3 days + 5-day forecast)
  python scripts/score_ward.py AMC-29 --start 2024-05-15 --end 2024-05-28   # historical replay
  python scripts/score_ward.py AMC-29 --date 2024-05-23     # explain one day in detail
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from heatrisk import load_config  # noqa: E402
from heatrisk.pipeline import load_wards, score_ward  # noqa: E402
from heatrisk.weather import fetch_archive, fetch_forecast  # noqa: E402

COLS = ["tmax", "tmin", "utci", "wbgt", "heat_index", "htsi", "htsi_category", "mri", "alert_mri", "hri", "alert_hri"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ward_id")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--date", help="day to explain in detail (default: highest-MRI day)")
    args = ap.parse_args()

    cfg, wards = load_config(), load_wards()
    ward = wards.set_index("ward_id").loc[args.ward_id]
    lat, lon = ward["centroid_lat"], ward["centroid_lon"]
    if args.start and args.end:
        wx = fetch_archive(lat, lon, args.start, args.end)
    else:
        wx = fetch_forecast(lat, lon)

    res = score_ward(args.ward_id, wx, wards, cfg)
    daily = res["daily"]
    print(f"\n{args.ward_id} {ward['ward_name']} ({ward['zone']} zone) — PVI {res['pvi']['pvi']:.1f}/100\n")
    print(daily[COLS].round(1).to_string())

    day = pd.Timestamp(args.date) if args.date else daily["mri"].idxmax()
    for target in ("mri", "hri"):
        e = res["explanations"][day][target]
        print(f"\n{target.upper()} on {day.date()}: {e.summary()}")
        for c in e.ranked():
            if abs(c.points) < 0.05 and not c.note:
                continue
            note = f"  ({c.note})" if c.note else ""
            print(f"  {c.points:6.1f}  {c.label} [{c.data_label}]{note}")
    print("\nAll scores are model estimates, not clinical predictions.")


if __name__ == "__main__":
    main()
