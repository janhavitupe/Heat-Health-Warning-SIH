"""Run refresh jobs by hand.

  python -m api.cli wards            reload ward geometry and attributes
  python -m api.cli forecast         deterministic forecast for every ward
  python -m api.cli ensemble         ensemble probabilities (~4 min)
  python -m api.cli replay may2024   build a replay (archive weather + lagged-ensemble probabilities)
  python -m api.cli all              wards + forecast + ensemble + all replays
"""

from __future__ import annotations

import logging
import sys
import time

from api import db, jobs


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not argv:
        sys.exit(__doc__)
    cmd = argv[0]
    with db.connect() as conn:
        db.init(conn)
        steps = {
            "wards": lambda: jobs.load_wards_table(conn),
            "forecast": lambda: jobs.run_forecast(conn),
            "ensemble": lambda: jobs.run_ensemble(conn),
            "replay": lambda: jobs.build_replay(conn, argv[1] if len(argv) > 1 else "may2024"),
        }
        order = ["wards", "forecast", "ensemble"] if cmd == "all" else [cmd]
        for step in order:
            if step not in steps:
                sys.exit(__doc__)
            t = time.time()
            steps[step]()
            print(f"{step}: done in {time.time() - t:.0f}s")
        if cmd == "all":
            for name in jobs.REPLAYS:
                t = time.time()
                jobs.build_replay(conn, name)
                print(f"replay {name}: done in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
