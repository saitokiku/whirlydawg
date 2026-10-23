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


# ---------------------------------------------------------------- blade bow --
def bow_offset(z: np.ndarray | float, s: float, H: float):
    """Normal offset of the blade mid-surface at height z above the lower cap face."""
    return s * np.sin(np.pi * np.asarray(z) / H) ** 2


def bow_slope(z, s, H):
    return s * np.pi / H * np.sin(2 * np.pi * np.asarray(z) / H)


def bow_arc_length(s: float, H: float, n: int = 4001) -> float:
    z = np.linspace(0.0, H, n)
    return float(np.trapezoid(np.sqrt(1.0 + bow_slope(z, s, H) ** 2), z))


def solve_cap_separation(developed_length: float, s: float) -> float:
    """Projected (vertical) distance between the two shoulders for a given flat length."""
    if s <= 0:
        return developed_length
    lo, hi = developed_length * 0.6, developed_length
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if bow_arc_length(s, mid) > developed_length:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


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


def blade_points(i: int, P: dict, D: dict, nu: int = 40, nz: int = 61):
    """Sample both faces of blade i body (no tabs). Returns array (k, 3)."""
    T, c, n = blade_frame(i, P, D)
    t = P["blade"]["thickness"]
    u = np.linspace(D["blade_u_inner"], D["blade_u_outer"], nu)
    z = np.linspace(0, D["cap_separation"], nz)
    U, Z = np.meshgrid(u, z)
    pts = []
    for side in (-0.5, 0.5):
        d = bow_offset(Z, P["blade"]["bow_sagitta"], D["cap_separation"]) + side * t
        X = T[0] + U * c[0] + d * n[0]
        Y = T[1] + U * c[1] + d * n[1]
        pts.append(np.stack([X.ravel(), Y.ravel(), (Z + D["z_lower_face"]).ravel()], 1))
    return np.concatenate(pts)


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

    # blade developed geometry
    dev = B["blank_length"] - 2 * B["tab_length"]
    D["blade_developed_body_length"] = dev
    H = solve_cap_separation(dev, B["bow_sagitta"])
    D["cap_separation"] = H
    D["blade_u_inner"] = -(B["tab_inner_margin"] + B["tab_width"] / 2)
    D["blade_u_outer"] = D["blade_u_inner"] + B["body_chord"]
    D["tab_u_range"] = [-B["tab_width"] / 2, B["tab_width"] / 2]
    D["bow_max_slope_deg"] = math.degrees(math.atan(B["bow_sagitta"] * math.pi / H))
    D["bow_min_bend_radius"] = H ** 2 / (2 * math.pi ** 2 * B["bow_sagitta"]) if B["bow_sagitta"] else None
    D["pocket_length"] = B["tab_width"] + K["length_clearance_total"]
    D["tab_bottom_clearance_in_pocket"] = K["depth"] - B["tab_length"]

    # pocket shell check (outermost pocket corner incl. mouth chamfer)
    T, c, n = blade_frame(0, P, D)
    corners = []
    for su in (-1, 1):
        for sn in (-1, 1):
            corners.append(T + su * (D["pocket_length"] / 2 + K["mouth_end_chamfer"]) * c
                           + sn * (K["width"] / 2 + K["mouth_side_lead_in"]) * n)
            corners.append(T + su * (D["pocket_length"] / 2) * c + sn * (K["width"] / 2) * n)
    r_pocket_max = max(float(np.hypot(*p)) for p in corners)
    r_pocket_max_deep = max(float(np.hypot(*(T + su * D["pocket_length"] / 2 * c + sn * K["width"] / 2 * n)))
                            for su in (-1, 1) for sn in (-1, 1))
    D["pocket_outer_radius_at_mouth"] = r_pocket_max
    D["pocket_outer_radius_below_lead_in"] = r_pocket_max_deep
    D["upper_hub_shell_outside_pocket"] = UH["od"] / 2 - r_pocket_max          # at the chamfered mouth (worst)
    D["lower_hub_shell_outside_pocket"] = LH["od"] / 2 - r_pocket_max
    D["upper_hub_shell_outside_pocket_below_mouth"] = UH["od"] / 2 - r_pocket_max_deep
    D["upper_hub_roof_over_pocket"] = UH["thickness"] - K["depth"]
    D["lower_hub_floor_under_pocket"] = LH["thickness"] - K["depth"]

    # where the blade bottom edge reaches (end of chord, at the cap faces)
    p_out = T + D["blade_u_outer"] * c
    p_in = T + D["blade_u_inner"] * c
    D["blade_end_outer_radius"] = float(np.hypot(*p_out))
    D["blade_end_inner_radius"] = float(np.hypot(*p_in))

    # vertical stack (roof surface at axis = 0)
    z_ct, lift_terms = roof_lift(P, LH["od"] / 2, D["blade_end_outer_radius"] + B["thickness"])
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
    D["z_shaft_top"] = D["z_upper_bore_top"] - SH["top_clearance_in_blind_bore"]
    D["shaft_length"] = D["z_shaft_top"] - D["z_shaft_bottom"]
    D["shaft_fits_user_tube_length"] = D["shaft_length"] <= SH["user_tube_length"]
    D["z_upper_set_screw"] = D["z_upper_face"] - HF["upper_screw_below_face"]
    D["z_lower_set_screw"] = D["z_lower_face"] + HF["lower_screw_above_face"]
    D["set_screw_axis_spacing"] = D["z_upper_set_screw"] - D["z_lower_set_screw"]
    D["z_lower_boss_top"] = D["z_lower_face"] + LH["boss_top_above_face"]
    D["z_upper_boss_bottom"] = D["z_upper_face"] - UH["boss_length_below_face"]
    D["z_chimney_top"] = D["z_lower_face"] + LH["chimney_height_above_face"]
    D["z_support_ring_bottom"] = z_ct - S["support_ring_height"]
    D["tower_length"] = D["z_tower_top"] - D["z_tower_bottom"]
    D["tower_below_roof"] = -D["z_tower_bottom"]

    # rotor envelope
    pts = blade_points(0, P, D)
    r = np.hypot(pts[:, 0], pts[:, 1])
    D["rotor_od_actual"] = float(2 * r.max())
    D["rotor_od_at_cap_faces"] = float(2 * (np.hypot(*p_out) + 0))
    D["rotor_od_vs_target"] = D["rotor_od_actual"] - P["rotor_target_od"]
    D["blade_inner_radius_min"] = float(r.min())

    # neighbour clearance (sampled) and plan coverage
    p1 = blade_points(1, P, D, nu=60, nz=81)
    p0 = blade_points(0, P, D, nu=60, nz=81)
    best = 1e9
    for zv in np.unique(p0[:, 2])[::2]:
        a = p0[np.isclose(p0[:, 2], zv)][:, :2]
        b = p1[np.isclose(p1[:, 2], zv)][:, :2]
        if len(a) and len(b):
            dmin = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)).min()
            best = min(best, float(dmin))
    D["neighbour_min_clearance_sampled"] = best
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
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
        "Cap separation %.2f mm assumes the formed bow equals %.1f mm; actual separation is set at assembly by seating the upper hub on the blade shoulders." % (D["cap_separation"], P["blade"]["bow_sagitta"]),
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
