"""Build the summer thermal-stress climatology used to calibrate HTSI (Phase 3).

Fetches hourly Open-Meteo archive (ERA5) weather at the city centre for the
configured summer months of each reference year, runs it through the same
thermal code as the live pipeline, and stores one row per day with the daily
indicators (mean of the 3 hottest hours) plus Tmax/Tmin.

Output: data/processed/climatology_daily.parquet
Usage:  python scripts/build_climatology.py [--start 1991 --end 2020]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from heatrisk import indices, load_config, thermal  # noqa: E402
from heatrisk.config import ROOT  # noqa: E402
from heatrisk.weather import fetch_archive  # noqa: E402

OUT = ROOT / "data" / "processed" / "climatology_daily.parquet"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1991)
    ap.add_argument("--end", type=int, default=2020)
    args = ap.parse_args()

    cfg = load_config()
    lat, lon = cfg["city"]["centre"]["lat"], cfg["city"]["centre"]["lon"]
    months = cfg["downscaling"]["lst_season_months"]
    frames = []
    for yr in range(args.start, args.end + 1):
        start = f"{yr}-{min(months):02d}-01"
        end = (pd.Timestamp(yr, max(months), 1) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        for attempt in range(3):
            try:
                wx = fetch_archive(lat, lon, start, end)
                break
            except Exception as e:  # network hiccups / rate limits
                print(f"  {yr}: {e}; retrying")
                time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError(f"could not fetch {yr}")
        hourly = thermal.compute(wx, lat, lon, cfg)
        frames.append(indices.daily_indicators(hourly, cfg))
        print(f"{yr}: {len(frames[-1])} days", flush=True)

    daily = pd.concat(frames)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(OUT)
    print(f"Wrote {len(daily)} days to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
