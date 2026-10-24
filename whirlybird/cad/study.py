"""Variant study: blade count x plan chord angle x cup radius (spec sections 3, 4, 13).
Every variant is re-fitted (tab radius) so its blade tips reach the same rotor OD as the baseline."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from params import derive, fit_tab_radius, load_inputs, variant  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports"


def fitted(P0, **changes):
    r_tip = derive(P0)["rotor_od_actual"] / 2
    P = fit_tab_radius(variant(P0, **changes), r_tip)
    return P, derive(P)


def row(P, D):
    return {
        "blades": P["blade_count"],
        "chord_angle_deg": P["blade"]["plan_chord_angle_from_radial"],
        "cup_radius_mm": P["blade"]["cup_radius"],
        "tab_radius_mm": round(P["pocket"]["tab_center_radius"], 1),
        "rotor_od_mm": round(D["rotor_od_actual"], 1),
        "air_channel_mm": round(D["neighbour_min_clearance_sampled"], 1),
        "plan_coverage_pct": round(100 * D["plan_coverage_fraction"], 1),
        "cup_depth_mm": round(D["cup_depth"], 1),
        "pocket_wall_mm": round(D["upper_hub_shell_outside_pocket"], 2),
        "blade_set_mass_g": round(D["blade_mass_g"] * P["blade_count"], 0),
        "stock_pieces": -(-P["blade_count"] // 4),
        "installed_height_mm": round(D["installed_height"], 1),
        "meets_targets": D["plan_coverage_fraction"] >= 1.0 and D["neighbour_min_clearance_sampled"] >= 10.0
                         and D["upper_hub_shell_outside_pocket"] >= P["pocket"]["min_exterior_shell"],
    }


def main(verbose=True):
    P0 = load_inputs()
    rows = []
    for n in (16, 20, 24):
        for th in (45, 55, 65):
            for rc in (40, 45, 60):
                P, D = fitted(P0, blade_count=n, **{"blade.plan_chord_angle_from_radial": th, "blade.cup_radius": rc})
                rows.append(row(P, D))
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
