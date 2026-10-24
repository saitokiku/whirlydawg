"""Parameter loading and derived-dimension calculation for the doghouse whirlybird.

Every dimension used by the CAD comes from MASTER_PARAMETERS.json "inputs".
This module turns those inputs into the coupled numbers (cap separation from the
blade bow, the vertical Z stack, shaft length, rotor OD, roof-pitch lift) and
writes them back under "derived" so the parameter file is the single report.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PARAM_FILE = ROOT / "MASTER_PARAMETERS.json"


def load_inputs(path: Path = PARAM_FILE) -> dict:
    with open(path) as f:
        return json.load(f)["inputs"]


# ---------------------------------------------------------------- blade cup --
# The blade is straight vertically and curved across its width (in plan) on cup_radius Rc,
# like a traditional turbine-vent vane. s = arc length across the width measured from the tab
# centre T; positive s runs along the chord direction c (outward). The cup centre of curvature
# is C = T + k*Rc*n (k = cup_direction), so the concave face looks toward +k*n.


def arc_point(T, c, n, k, Rc, s, off=0.0):
    """Global XY of the point at arc length s from T, offset `off` away from the cup centre."""
    phi = np.asarray(s, float) / Rc
    C = T + k * Rc * n
    R = Rc + off
    return C + np.multiply.outer(R * np.sin(phi), c) - np.multiply.outer(k * R * np.cos(phi), n)


def cup_geometry(P):
    B = P["blade"]
    Rc, W = B["cup_radius"], B["body_chord"]
    ang = W / Rc
    return {"cup_angle_deg": math.degrees(ang), "cup_chord": 2 * Rc * math.sin(ang / 2),
            "cup_depth": Rc * (1 - math.cos(ang / 2))}


# ------------------------------------------------------------- plan layout --
def blade_frame(i: int, P: dict, D: dict):
    """Return (T, c, n) for blade i in global XY: tab centre, chord dir, outward normal."""
    phi = 2 * math.pi * i / P["blade_count"]
    th = math.radians(P["blade"]["plan_chord_angle_from_radial"])
    rho = P["pocket"]["tab_center_radius"]
    T = np.array([rho * math.cos(phi), rho * math.sin(phi)])
    c = np.array([math.cos(phi + th), math.sin(phi + th)])
    n = np.array([math.cos(phi + th - math.pi / 2), math.sin(phi + th - math.pi / 2)])
    return T, c, n


def blade_plan_points(i: int, P: dict, D: dict, ns: int = 121):
    """Plan (XY) samples of both faces of blade i body. Returns array (k, 2)."""
    T, c, n = blade_frame(i, P, D)
    B = P["blade"]
    sv = np.linspace(D["blade_u_inner"], D["blade_u_outer"], ns)
    return np.concatenate([arc_point(T, c, n, B["cup_direction"], B["cup_radius"], sv, off)
                           for off in (-B["thickness"] / 2, 0.0, B["thickness"] / 2)])


def blade_points(i: int, P: dict, D: dict, ns: int = 61, nz: int = 5):
    """3-D samples of blade i body faces (blade is vertical, so z only repeats the plan)."""
    xy = blade_plan_points(i, P, D, ns)
    zs = np.linspace(0, D["cap_separation"], nz) + D["z_lower_face"]
    return np.concatenate([np.column_stack([xy, np.full(len(xy), z)]) for z in zs])


def roof_lift(P: dict, r_hub: float, r_blade_bottom: float) -> tuple[float, dict]:
    """Collar-top height at the axis required for a given roof pitch."""
    S = P["stationary"]
    tp = math.tan(math.radians(P["roof_pitch_deg"]))
    gap = S["rotor_to_stationary_axial_gap"]
    r_cb = S["throat_id"] / 2 + S["support_ring_wall"] + 0.1
    cands = {
        "collar_min_at_axis": S["collar_height_above_roof_min"],
        "counterbore_above_uphill_roof": r_cb * tp + S["support_ring_height"] + 2.0,
        "lower_hub_rim_clear_of_roof": r_hub * tp + gap - gap,
        "blade_bottom_clear_of_roof": r_blade_bottom * tp + gap - (gap + P["lower_hub"]["thickness"]),
    }
    return max(cands.values()), cands


def derive(P: dict) -> dict:
    B, K, UH, LH, SH = P["blade"], P["pocket"], P["upper_hub"], P["lower_hub"], P["shaft"]
    BR, S, HF = P["bearings"], P["stationary"], P["hub_fixing"]
    D: dict = {}

    # blade developed geometry (no vertical bow: the shoulders are one blank-body length apart)
    dev = B["blank_length"] - 2 * B["tab_length"]
    D["blade_developed_body_length"] = dev
    H = dev
    D["cap_separation"] = H
    D["blade_u_inner"] = -(B["tab_inner_margin"] + B["tab_width"] / 2)
    D["blade_u_outer"] = D["blade_u_inner"] + B["body_chord"]
    D["tab_u_range"] = [-B["tab_width"] / 2, B["tab_width"] / 2]
    D.update(cup_geometry(P))
    D["pocket_length"] = B["tab_width"] + K["length_clearance_total"]
    D["tab_bottom_clearance_in_pocket"] = K["depth"] - B["tab_length"]

    # pocket shell check (outermost pocket point incl. mouth lead-in; pocket follows the cup arc)
    T, c, n = blade_frame(0, P, D)
    k, Rc = B["cup_direction"], B["cup_radius"]
    Lp = D["pocket_length"]
    mouth = arc_point(T, c, n, k, Rc, np.linspace(-Lp / 2 - K["mouth_end_chamfer"], Lp / 2 + K["mouth_end_chamfer"], 41),
                      0.0)
    mouth = np.concatenate([arc_point(T, c, n, k, Rc, np.linspace(-Lp / 2 - K["mouth_end_chamfer"], Lp / 2 + K["mouth_end_chamfer"], 41), o)
                            for o in (-(K["width"] / 2 + K["mouth_side_lead_in"]), K["width"] / 2 + K["mouth_side_lead_in"])])
    deep = np.concatenate([arc_point(T, c, n, k, Rc, np.linspace(-Lp / 2, Lp / 2, 41), o)
                           for o in (-K["width"] / 2, K["width"] / 2)])
    r_pocket_max = float(np.hypot(*mouth.T).max())
    r_pocket_max_deep = float(np.hypot(*deep.T).max())
    D["pocket_outer_radius_at_mouth"] = r_pocket_max
    D["pocket_outer_radius_below_lead_in"] = r_pocket_max_deep
    D["upper_hub_shell_outside_pocket"] = UH["od"] / 2 - r_pocket_max          # at the chamfered mouth (worst)
    D["lower_hub_shell_outside_pocket"] = LH["od"] / 2 - r_pocket_max
    D["upper_hub_shell_outside_pocket_below_mouth"] = UH["od"] / 2 - r_pocket_max_deep
    D["upper_hub_roof_over_pocket"] = UH["thickness"] - K["depth"]
    D["lower_hub_floor_under_pocket"] = LH["thickness"] - K["depth"]

    # where the blade edges are
    D["blade_end_outer_radius"] = float(np.hypot(*arc_point(T, c, n, k, Rc, D["blade_u_outer"])))
    D["blade_end_inner_radius"] = float(np.hypot(*arc_point(T, c, n, k, Rc, D["blade_u_inner"])))

    # vertical stack (roof surface at axis = 0)
    r_blade_max = float(np.hypot(*blade_plan_points(0, P, D).T).max())
    z_ct, lift_terms = roof_lift(P, LH["od"] / 2, r_blade_max)
    D["roof_lift_terms"] = lift_terms
    gap = S["rotor_to_stationary_axial_gap"]
    D["z_collar_top"] = z_ct
    D["z_lower_hub_bottom"] = z_ct + gap
    D["z_lower_face"] = D["z_lower_hub_bottom"] + LH["thickness"]
    D["z_upper_face"] = D["z_lower_face"] + H
    D["z_rotor_top"] = D["z_upper_face"] + UH["thickness"]
    D["installed_height"] = D["z_rotor_top"]
    D["height_margin_to_limit"] = P["max_installed_height"] - D["installed_height"]

    # bearings / tower
    D["z_upper_bearing_top"] = D["z_lower_hub_bottom"] + 6.0
    D["z_cup_ceiling"] = D["z_upper_bearing_top"] + S["thrust_washer_top"]
    D["z_upper_bearing_center"] = D["z_upper_bearing_top"] - BR["width"] / 2
    D["z_lower_bearing_center"] = D["z_upper_bearing_center"] - BR["center_separation"]
    D["z_tower_bottom"] = D["z_lower_bearing_center"] - BR["width"] / 2
    D["z_tower_top"] = D["z_upper_bearing_top"]
    D["z_washer_bottom_bottom"] = D["z_tower_bottom"] - S["thrust_washer_bottom"]
    D["z_collar_top_face"] = D["z_washer_bottom_bottom"] - S["collar_endplay"]
    D["z_collar_bottom_face"] = D["z_collar_top_face"] - S["shaft_collar_width"]
    D["z_shaft_bottom"] = D["z_collar_bottom_face"] - SH["below_collar_extension"]
    D["z_upper_bore_top"] = D["z_upper_face"] + UH["thickness"] - D["upper_hub_roof_over_pocket"]
    # upper hub is held down by an M4 tie rod through the hollow shaft into a captive nut
    D["z_upper_nut_bottom"] = D["z_upper_face"] + HF["upper_nut_bottom_above_face"]
    D["z_upper_nut_top"] = D["z_upper_nut_bottom"] + 3.2
    D["z_shaft_top"] = D["z_upper_nut_bottom"] - SH["top_gap_below_upper_nut"]
    D["shaft_length"] = D["z_shaft_top"] - D["z_shaft_bottom"]
    D["shaft_fits_user_tube_length"] = D["shaft_length"] <= SH["user_tube_length"]
    D["z_tie_rod_top"] = D["z_upper_nut_top"] + HF["tie_rod_above_upper_nut"]
    D["z_tie_rod_bottom"] = D["z_shaft_bottom"] - HF["tie_rod_below_tube"]
    D["tie_rod_length"] = D["z_tie_rod_top"] - D["z_tie_rod_bottom"]
    D["tie_rod_top_clear_of_bore_top"] = D["z_upper_bore_top"] - D["z_tie_rod_top"]
    D["z_lower_set_screw"] = D["z_lower_face"] + HF["lower_screw_above_face"]
    D["z_lower_boss_top"] = D["z_lower_face"] + LH["boss_top_above_face"]
    D["z_upper_boss_bottom"] = D["z_upper_face"] - UH["boss_length_below_face"]
    D["z_chimney_top"] = D["z_lower_face"] + LH["chimney_height_above_face"]
    D["z_support_ring_bottom"] = z_ct - S["support_ring_height"]
    D["tower_length"] = D["z_tower_top"] - D["z_tower_bottom"]
    D["tower_below_roof"] = -D["z_tower_bottom"]

    # rotor envelope, neighbour clearance (blades are vertical: one plan slice is exact)
    xy0 = blade_plan_points(0, P, D)
    xy1 = blade_plan_points(1, P, D)
    r = np.hypot(xy0[:, 0], xy0[:, 1])
    D["rotor_od_actual"] = float(2 * r.max())
    D["rotor_od_at_cap_faces"] = D["rotor_od_actual"]
    D["rotor_od_vs_target"] = D["rotor_od_actual"] - P["rotor_target_od"]
    D["blade_inner_radius_min"] = float(r.min())
    D["blade_ring_radial_band"] = [float(r.min()), float(r.max())]
    D["neighbour_min_clearance_sampled"] = float(np.sqrt(((xy0[:, None, :] - xy1[None, :, :]) ** 2).sum(-1)).min())
    D["air_channel_width_between_blades"] = D["neighbour_min_clearance_sampled"]
    az = np.degrees(np.arctan2(xy0[:, 1], xy0[:, 0]))
    D["blade_plan_angular_span_deg"] = float(az.max() - az.min())
    D["plan_coverage_fraction"] = D["blade_plan_angular_span_deg"] / (360.0 / P["blade_count"])

    # masses
    t = B["thickness"]
    blade_area = B["body_chord"] * dev + 2 * B["tab_width"] * B["tab_length"]
    D["blade_flat_area_mm2"] = blade_area
    D["blade_mass_g"] = blade_area * t * B["density_g_cm3"] / 1000.0

    # centrifugal design check at 1000 rpm
    w = 1000 * 2 * math.pi / 60
    r_cg = float(r.mean()) / 1000.0
    F = D["blade_mass_g"] / 1000.0 * r_cg * w ** 2
    D["centrifugal_check"] = {
        "rpm": 1000, "blade_cg_radius_mm": r_cg * 1000, "force_per_blade_N": F,
        "force_per_tab_N": F / 2,
        "tab_bearing_stress_MPa": (F / 2) / (t * B["tab_length"]),
        "proof_pull_target_N": 50.0,
        "proof_vs_1000rpm_ratio": 50.0 / (F / 2),
    }
    return D


def unresolved(P: dict, D: dict) -> list[str]:
    u = [
        "Roof pitch is unknown: CAD built at roof_pitch_deg=%.1f. Adapters for 0, 2/12, 3/12, 4/12 and 5/12 are exported; measure and rebuild." % P["roof_pitch_deg"],
        "Roof deck thickness assumed %.0f mm (only affects tower clearance below the deck)." % P["roof_deck_thickness"],
        "Pocket width %.2f mm is a placeholder until the 1.85/1.95/2.05/2.15 coupon is tested with your actual aluminium." % P["pocket"]["width"],
        "Bearing seat bore %.2f mm and hub shaft bore %.2f mm are placeholders until the bearing/shaft fit coupon is tested." % (P["bearings"]["seat_bore_diameter"], P["shaft"]["hub_bore_diameter"]),
        "Bearing bore not verified: confirm the R4-2RS markings and that the chosen shaft slips through both inner races without force.",
        "Forming-die springback factor %.2f is a first guess; the alloy/temper of the 1.6 mm sheet is unknown." % P["forming_die"]["springback_factor"],
        "Cap separation %.2f mm = blank body length; cut blanks to length within +/-0.2 mm. The tie rod pulls the upper hub onto the shoulders, so small length differences are taken up as light compression." % D["cap_separation"],
        "Cup radius %.0f mm: the 1:1 cup gauge checks it; 20 blades need 5 pieces of 11.75 x 3.75 in stock (4 blanks per piece)." % P["blade"]["cup_radius"],
        "Shaft must be HOLLOW (your 1/4 in tube, ID %.2f) so the M4 tie rod passes; verify the tube slips into both bearings." % P["shaft"]["tube_id"],
        "Airflow, rpm and rain ingress are not predicted by this CAD; they must be measured (spec gates E and F).",
    ]
    if not D["shaft_fits_user_tube_length"]:
        u.append("Shaft length %.1f mm exceeds the user tube (%.1f mm)." % (D["shaft_length"], P["shaft"]["user_tube_length"]))
    return u


def write_report(P: dict, D: dict, path: Path = PARAM_FILE) -> None:
    with open(path) as f:
        doc = json.load(f)
    doc["derived"] = _round(D)
    doc["unresolved"] = unresolved(P, D)
    with open(path, "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")


def _round(x):
    if isinstance(x, float):
        return round(x, 3)
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v) for v in x]
    return x


def fit_tab_radius(P: dict, r_tip: float) -> dict:
    """Copy of P with pocket.tab_center_radius chosen so the outermost blade point sits at r_tip."""
    Q = copy.deepcopy(P)
    lo, hi = 40.0, r_tip
    for _ in range(50):
        Q["pocket"]["tab_center_radius"] = 0.5 * (lo + hi)
        D = {"blade_u_inner": -(Q["blade"]["tab_inner_margin"] + Q["blade"]["tab_width"] / 2)}
        D["blade_u_outer"] = D["blade_u_inner"] + Q["blade"]["body_chord"]
        r = float(np.hypot(*blade_plan_points(0, Q, D).T).max())
        lo, hi = (Q["pocket"]["tab_center_radius"], hi) if r < r_tip else (lo, Q["pocket"]["tab_center_radius"])
    return Q


def variant(P: dict, **changes) -> dict:
    """Copy of inputs with dotted-key overrides, e.g. variant(P, **{"blade.bow_sagitta": 10})."""
    Q = copy.deepcopy(P)
    for k, v in changes.items():
        node = Q
        parts = k.split(".")
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = v
    return Q


if __name__ == "__main__":
    P = load_inputs()
    D = derive(P)
    for k, v in D.items():
        print(f"{k:40s} {v}")
