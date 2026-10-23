"""Variant study: plan chord angle x bow sagitta x blade count (spec sections 3, 4, 13)."""
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from params import load_inputs, derive, variant  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports"


def row(P, D):
    return {
        "blades": P["blade_count"],
        "chord_angle_deg": P["blade"]["plan_chord_angle_from_radial"],
        "bow_sagitta_mm": P["blade"]["bow_sagitta"],
        "cap_separation_mm": round(D["cap_separation"], 2),
        "installed_height_mm": round(D["installed_height"], 1),
        "rotor_od_mm": round(D["rotor_od_actual"], 1),
        "od_at_cap_faces_mm": round(D["rotor_od_at_cap_faces"], 1),
        "neighbour_clearance_mm": round(D["neighbour_min_clearance_sampled"] - P["blade"]["thickness"], 1),
        "plan_coverage_pct": round(100 * D["blade_plan_angular_span_deg"] * P["blade_count"] / 360, 1),
        "min_bend_radius_mm": round(D["bow_min_bend_radius"], 1),
        "max_bow_slope_deg": round(D["bow_max_slope_deg"], 1),
        "blade_set_mass_g": round(D["blade_mass_g"] * P["blade_count"], 0),
        "pocket_shell_mm": round(D["upper_hub_shell_outside_pocket"], 2),
    }


def main(verbose=True):
    P0 = load_inputs()
    rows = []
    for n in (8, 10, 12):
        for th in (25, 35, 45):
            for s in (10, 15, 20):
                P = variant(P0, blade_count=n, **{"blade.plan_chord_angle_from_radial": th,
                                                   "blade.bow_sagitta": s})
                rows.append(row(P, derive(P)))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "variant_study.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if verbose:
        for r in rows:
            print(r)
    return rows


if __name__ == "__main__":
    main()
