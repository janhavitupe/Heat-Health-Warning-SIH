"""Action Recommendation Engine (Phase 6).

Turns each ward-day's alert level and the drivers behind its score into concrete
actions for AMC departments, using the rule table in resources/actions.yaml
(wording and departments from the Ahmedabad Heat Action Plan 2019).

  ward_actions(...)    actions for one ward-day, each with department, lead time and reason
  city_actions(...)    city-wide measures for a day (from the worst ward's level)
  priority_ranking(...) wards ordered by MRI (municipal) or HRI (healthcare), P(Red) breaking ties
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
import yaml

from heatrisk.config import ROOT

RULES_PATH = ROOT / "resources" / "actions.yaml"
LEVELS = ["green", "yellow", "orange", "red"]


@lru_cache(maxsize=1)
def load_rules(path: str = str(RULES_PATH)) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _level_ok(rule: dict, day: dict) -> bool:
    return _in_band(rule, day[f"alert_{rule.get('target', 'mri')}"])


def _in_band(rule: dict, level: str) -> bool:
    i = LEVELS.index(level)
    return LEVELS.index(rule["level"]) <= i <= LEVELS.index(rule.get("until", "red"))


def _condition_ok(rule: dict, day: dict, contributions: dict[str, float], ranks: dict[str, float],
                  ward: dict) -> bool:
    cond = rule.get("when")
    if not cond:
        return True
    if "contribution" in cond:
        return contributions.get(cond["contribution"], 0.0) >= cond["min_points"]
    if "attribute" in cond:
        return ranks.get(cond["attribute"], 0.0) >= cond["min_rank"]
    if "flag" in cond:
        return bool(ward.get(cond["flag"]))
    if "min_hot_days" in cond:
        return (day.get("hot_run_days") or 0) >= cond["min_hot_days"]
    if "metric" in cond:
        return (day.get(cond["metric"]) or float("-inf")) >= cond["min"]
    raise ValueError(f"unknown condition in rule {rule['id']}: {cond}")


def attribute_ranks(wards: pd.DataFrame) -> pd.DataFrame:
    """Percentile rank (0-1) of each numeric ward column across the city, for `min_rank` conditions."""
    num = wards.set_index("ward_id").select_dtypes("number")
    return (num.rank(method="average") - 1) / (len(num) - 1)


def ward_actions(day: dict, explanation: dict | None, ward: dict, ranks: dict[str, float],
                 rules: dict | None = None) -> list[dict]:
    """Ward-scope actions for one ward-day. `explanation` is the MRI explanation dict (forecast.explanation_dict)."""
    rules = rules or load_rules()
    contributions = {c["key"]: c["points"] for c in (explanation or {}).get("contributions", [])}
    out = []
    for r in rules["rules"]:
        if r["scope"] != "ward" or not _level_ok(r, day) or not _condition_ok(r, day, contributions, ranks, ward):
            continue
        out.append({"id": r["id"], "department": r["department"], "action": r["action"], "reason": r["reason"],
                    "lead": r["lead"], "level": r["level"], "target": r.get("target", "mri")})
    return out


def city_actions(worst_level: str, rules: dict | None = None) -> list[dict]:
    rules = rules or load_rules()
    return [{"id": r["id"], "department": r["department"], "action": r["action"], "reason": r["reason"],
             "lead": r["lead"], "level": r["level"]}
            for r in rules["rules"]
            if r["scope"] == "city" and _in_band(r, worst_level)]


def trigger_actions(action_key: str, rules: dict | None = None) -> list[dict]:
    """Preparedness actions for a probability trigger (e.g. "orange_preparedness")."""
    rules = rules or load_rules()
    return rules.get("triggers", {}).get(action_key, [])


def priority_ranking(day_rows: pd.DataFrame, view: str = "municipal") -> pd.DataFrame:
    """Wards for one day, most urgent first: MRI (municipal) or HRI (healthcare); P(Red) breaks ties."""
    score = "hri" if view == "healthcare" else "mri"
    df = day_rows.copy()
    if "p_red" not in df:
        df["p_red"] = float("nan")
    df = df.sort_values([score, "p_red"], ascending=False, na_position="last").reset_index(drop=True)
    df["priority"] = range(1, len(df) + 1)
    return df
