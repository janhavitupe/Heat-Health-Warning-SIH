"""Exact, additive explanations of MRI / HRI — proposal §6.7.

The risk score is decomposed so that the contributions sum exactly to it:

  heat part           HTSI, split across HTSI components by their points
  vulnerability part  HTSI × spread × (PVI − 50)/50, split across PVI indicators by
                      each one's distance from its midpoint (neutral indicators give 0;
                      below-average vulnerability gives negative points)
  factor part         HTSI × mult × (F − 1)   (historical illness H_m or capacity C_h)

where F is H_m (for MRI) or C_h (for HRI) and mult is the vulnerability
multiplier. If HTSI or the risk score was capped at 100, every contribution is
scaled by the same ratio, so the sum still equals the reported score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from heatrisk.risk import vulnerability_multiplier

HEAT_LABELS = {
    "utci": ("Whole-body heat stress (UTCI)", "live"),
    "wbgt": ("Outdoor work heat stress (WBGT)", "live"),
    "heat_index": ("Heat + humidity (Heat Index)", "live"),
    "night": ("Hot night — little overnight recovery", "live"),
    "persist": ("Consecutive hot days", "live"),
    "indoor": ("Heat-trapping sheet roofs (indoor heat)", "census"),
}
PVI_LABELS = {
    "elderly_share": "Elderly population (60+)",
    "outdoor_worker_share": "Outdoor workers",
    "healthcare_access_gap": "Distance to hospital care",
    "informal_housing_share": "Informal housing",
    "under5_share": "Young children (under 5)",
    "population_density": "Population density",
}
FACTOR_LABELS = {"mri": ("Past heat-illness history (H_m)", "historical"),
                 "hri": ("Hospital capacity pressure (C_h)", "model_estimate")}


@dataclass
class Contribution:
    key: str
    label: str
    points: float
    group: str          # heat | vulnerability | factor
    data_label: str     # live | census | satellite_derived | historical | model_estimate
    note: str = ""


@dataclass
class Explanation:
    target: str
    score: float
    level: str
    contributions: list[Contribution] = field(default_factory=list)

    def ranked(self) -> list[Contribution]:
        return sorted(self.contributions, key=lambda c: abs(c.points), reverse=True)

    def summary(self, top: int = 2) -> str:
        drivers = [c for c in self.ranked() if c.points > 0][:top]
        parts = ", ".join(f"{c.label[0].lower() + c.label[1:]} (+{c.points:.0f} pts)" for c in drivers)
        return f"{self.level.title()} ({self.score:.0f}/100, model estimate) — driven by {parts}."


def explain_day(day: dict, pvi_row: dict, pvi_status: dict[str, str], factor: float,
                factor_defaulted: bool, target: str, cfg: dict) -> Explanation:
    """Explain one ward-day. `day` is a row of the scored daily table."""
    spread = cfg["risk"]["vulnerability_spread"]
    weights = cfg["pvi"]["weights"]
    pvi = pvi_row["pvi"]
    mult = vulnerability_multiplier(pvi, cfg)

    htsi_scale = day["htsi"] / day["htsi_raw"] if day["htsi_raw"] > 0 else 0.0
    raw_score = day[f"{target}_raw"]
    score_scale = day[target] / raw_score if raw_score > 0 else 0.0
    s = htsi_scale * score_scale

    contribs: list[Contribution] = []
    for key, (label, data_label) in HEAT_LABELS.items():
        pts = day[f"pts_{key}"] * s
        note = "roof data not yet available — counted as 0" if key == "indoor" and day["indoor_data_missing"] else ""
        contribs.append(Contribution(key, label, pts, "heat", data_label, note))

    for key, label in PVI_LABELS.items():
        above_mid = pvi_row[f"pvi_pts_{key}"] - 50.0 * weights[key]   # sums to PVI − 50
        pts = day["htsi_raw"] * spread * above_mid / 50.0 * s
        status = pvi_status.get(key, "used")
        note = "" if status == "used" else status.replace("neutral: ", "held at city midpoint — ")
        contribs.append(Contribution(key, label, pts, "vulnerability", "model_estimate", note))

    f_label, f_data = FACTOR_LABELS[target]
    contribs.append(Contribution(
        "factor", f_label, day["htsi_raw"] * mult * (factor - 1) * s, "factor", f_data,
        "no data — default 1.0" if factor_defaulted else "",
    ))

    return Explanation(target, float(day[target]), day[f"alert_{target}"], contribs)
