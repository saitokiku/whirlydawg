"""Design-gate checks on the real CAD (spec section 10A + 9): interference, clearances,
blind pockets, assembly sequence, access, height, printer bed fit."""
from __future__ import annotations

import itertools
import math

from build123d import Axis, Box, Cylinder, GeomType, Plane, Pos, Rot, Align

import geometry as g

INTENDED_CONTACT = {
    # pairs (name fragments) that legitimately touch / share a surface
    ("set_screw", "nut"), ("set_screw", "shaft"), ("inner_race", "outer_race"), ("inner_race", "seal"),
    ("outer_race", "seal"), ("inner_race", "shaft"), ("thrust_washer", "inner_race"),
    ("thrust_washer", "shaft"), ("shaft_collar", "shaft"), ("thrust_washer_bottom", "shaft_collar"),
    ("blade", "upper_hub"), ("blade", "lower_hub"), ("thrust_washer_top", "lower_hub"),
    ("outer_race", "bearing_support"), ("bearing_support", "roof_flash_adapter"),
    ("bearing_support", "rain_baffle"), ("nut", "upper_hub"), ("nut", "lower_hub"),
    ("set_screw", "upper_hub"), ("set_screw", "lower_hub"), ("shaft", "upper_hub"), ("shaft", "lower_hub"),
    ("tie_rod", "nut"), ("tie_rod", "washer"), ("tie_rod_washer", "shaft"), ("tie_rod", "shaft"),
}


def ivol(a, b) -> float:
    """Volume of the intersection of two solids (0 when they do not meet)."""
    r = a & b
    return 0.0 if r is None else float(r.volume)


def _contact_ok(a, b):
    for x, y in INTENDED_CONTACT:
        if (x in a and y in b) or (x in b and y in a):
            return True
    return False


def _bbox_overlap(a, b, pad=0.0):
    A, B = a.bounding_box(), b.bounding_box()
    return not (A.max.X + pad < B.min.X or B.max.X + pad < A.min.X or A.max.Y + pad < B.min.Y or
                B.max.Y + pad < A.min.Y or A.max.Z + pad < B.min.Z or B.max.Z + pad < A.min.Z)


def interference(items, tol_vol=1e-3):
    """Pairwise solid intersection volume (should be ~0 everywhere)."""
    rows = []
    for a, b in itertools.combinations(items, 2):
        if not _bbox_overlap(a.shape, b.shape):
            continue
        v = ivol(a.shape, b.shape)
        if v > tol_vol:
            rows.append((a.name, b.name, v, _contact_ok(a.name, b.name)))
    return rows


def rotor_stator_clearance(items):
    rot = [i for i in items if "rotating" in i.role]
    sta = [i for i in items if "stationary" in i.role]
    rows = []
    for a in rot:
        for b in sta:
            if not _bbox_overlap(a.shape, b.shape, pad=15.0):
                continue
            if _contact_ok(a.name, b.name) and ("race" in a.name or "seal" in b.name):
                continue
            d = a.shape.distance_to(b.shape)
            rows.append((a.name, b.name, d))
    rows.sort(key=lambda r: r[2])
    return rows


def blade_clearances(items, P):
    blades = [i for i in items if i.group == "blade"]
    n = len(blades)
    d_nb = min(blades[k].shape.distance_to(blades[(k + 1) % n].shape) for k in range(n))
    others = [i for i in items if i.group != "blade" and i.name not in ("upper_hub_closed_top", "lower_hub_closed_bottom")]
    rows = []
    for b in blades[:1]:
        for o in others:
            if _bbox_overlap(b.shape, o.shape, pad=20):
                rows.append((b.name, o.name, b.shape.distance_to(o.shape)))
    return d_nb, sorted(rows, key=lambda r: r[2])


def tab_in_pocket(P, D):
    """Clearance of one tab inside its blind pocket, both hubs (local analysis)."""
    K, B = P["pocket"], P["blade"]
    return {
        "side_clearance_each_side": (K["width"] - B["thickness"]) / 2,
        "end_clearance_each_end": (D["pocket_length"] - B["tab_width"]) / 2,
        "tab_tip_to_pocket_bottom": D["tab_bottom_clearance_in_pocket"],
        "engagement_depth": B["tab_length"],
    }


def pocket_blindness(items, P, D):
    """Distances from each pocket cavity to the exterior faces that must stay intact."""
    out = {}
    uh = next(i.shape for i in items if i.name == "upper_hub_closed_top")
    lh = next(i.shape for i in items if i.name == "lower_hub_closed_bottom")
    # upper: top face must be one planar face with no inner wires (closed); measure pocket->top & OD
    top_faces = [f for f in uh.faces() if f.geom_type == GeomType.PLANE and abs(f.center().Z - D["z_rotor_top"]) < 1e-3]
    out["upper_top_face_count"] = len(top_faces)
    out["upper_top_face_holes"] = sum(len(f.inner_wires()) for f in top_faces)
    bot_faces = [f for f in lh.faces() if f.geom_type == GeomType.PLANE and abs(f.center().Z - D["z_lower_hub_bottom"]) < 1e-3]
    out["lower_bottom_faces"] = len(bot_faces)
    pl0u = g.blade_plane(0, P, D, D["z_upper_face"])
    pl0l = g.blade_plane(0, P, D, D["z_lower_face"])
    from build123d import mirror
    tool_u = pl0u * mirror(g.pocket_tool_local(P, D), Plane.XY)
    tool_l = pl0l * g.pocket_tool_local(P, D)
    # exterior skins as thin probes
    R = P["upper_hub"]["od"] / 2
    top_probe = Pos(0, 0, D["z_rotor_top"]) * Cylinder(R, 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN))
    od_probe_u = Pos(0, 0, D["z_upper_face"]) * (Cylinder(R + 1, P["upper_hub"]["thickness"], align=(Align.CENTER, Align.CENTER, Align.MIN)) -
                                                  Cylinder(R, P["upper_hub"]["thickness"], align=(Align.CENTER, Align.CENTER, Align.MIN)))
    bot_probe = Pos(0, 0, D["z_lower_hub_bottom"] - 0.01) * Cylinder(R, 0.01, align=(Align.CENTER, Align.CENTER, Align.MIN))
    od_probe_l = Pos(0, 0, D["z_lower_hub_bottom"]) * (Cylinder(R + 1, P["lower_hub"]["thickness"], align=(Align.CENTER, Align.CENTER, Align.MIN)) -
                                                        Cylinder(R, P["lower_hub"]["thickness"], align=(Align.CENTER, Align.CENTER, Align.MIN)))
    clip_u = Pos(0, 0, D["z_upper_face"]) * Cylinder(R + 5, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    clip_l = Pos(0, 0, D["z_lower_hub_bottom"]) * Cylinder(R + 5, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    tu = tool_u & clip_u
    tl = tool_l & Pos(0, 0, D["z_lower_hub_bottom"]) * Cylinder(R + 5, P["lower_hub"]["thickness"], align=(Align.CENTER, Align.CENTER, Align.MIN))
    out["upper_pocket_to_top_face"] = tu.distance_to(top_probe)
    out["upper_pocket_to_OD"] = tu.distance_to(od_probe_u)
    out["lower_pocket_to_bottom_face"] = tl.distance_to(bot_probe)
    out["lower_pocket_to_OD_excluding_weep"] = tl.distance_to(od_probe_l)
    return out


def access_check(items, P, D):
    """Fixings must be reachable once the closed blade ring is assembled.
    Lower-hub set screw: tightened before blades go in (radial line clear of everything but blades).
    Upper hub: M4 tie rod nut sits below the bearing tower, so it is tightened from underneath."""
    res = {}
    blades = [i.shape for i in items if i.group == "blade"]
    others = [i.shape for i in items if i.group != "blade" and "rotating" in i.role and "hub" not in i.name
              and "tie_rod" not in i.name and "shaft" not in i.name and "set_screw" not in i.name and "nut" not in i.name]
    key = Rot(0, 0, g.SCREW_AZ) * Pos(P["lower_hub"]["boss_od"] / 2, 0, D["z_lower_set_screw"]) * Rot(0, 90, 0) * Cylinder(
        2.5, 150, align=(Align.CENTER, Align.CENTER, Align.MIN))
    res["lower_screw_key_path_clear_before_blades"] = min((key.distance_to(o) for o in others), default=99.0)
    res["lower_screw_above_chimney_top"] = D["z_lower_set_screw"] - 2.5 - D["z_chimney_top"]
    res["tie_rod_nut_below_tower_bottom"] = D["z_tower_bottom"] - (D["z_shaft_bottom"] - 1.2)
    res["tie_rod_top_clear_of_blind_bore_top"] = D["tie_rod_top_clear_of_bore_top"]
    nut = next(i.shape for i in items if i.name == "tie_rod_nyloc_nut_M4")
    sup = next(i.shape for i in items if i.name == "bearing_support_stationary")
    res["tie_rod_nut_to_stationary_support"] = nut.distance_to(sup)
    return res


def assembly_sequence(P, D, items):
    """Simulate the real assembly moves and report any collision along each path."""
    lh = next(i.shape for i in items if i.name == "lower_hub_closed_bottom")
    uh = next(i.shape for i in items if i.name == "upper_hub_closed_top")
    blades = [i.shape for i in items if i.group == "blade"]
    log = []
    # 1) each blade lowered vertically into the lower hub, others already seated
    for k, b in enumerate(blades):
        worst = 0.0
        for dz in (12.0, 8.0, 6.0, 4.0, 2.0, 1.0, 0.5, 0.0):
            mb = Pos(0, 0, dz) * b
            v = ivol(mb, lh)
            for j in range(k):
                v += ivol(mb, blades[j]) if _bbox_overlap(mb, blades[j]) else 0.0
            worst = max(worst, v)
        log.append((f"insert blade {k + 1} into lower hub (vertical drop 12 mm)", worst))
    # 2) upper hub lowered over all eight upper tabs
    worst = 0.0
    for dz in (14.0, 10.0, 8.0, 7.0, 6.0, 4.0, 2.0, 1.0, 0.5, 0.0):
        mu = Pos(0, 0, dz) * uh
        v = sum(ivol(mu, b) for b in blades)
        worst = max(worst, v)
    log.append(("lower upper hub onto 8 upper tabs (vertical, 14 mm travel)", worst))
    # 3) tabs remain trapped: with hubs fixed, a blade moved up by more than the tab clearance hits the upper hub
    b0 = blades[0]
    v_up = ivol(Pos(0, 0, 0.6) * b0, uh)
    v_rad = ivol(Pos(1.0, 0, 0) * b0, uh) + ivol(Pos(1.0, 0, 0) * b0, lh)
    log.append(("blade 1 lifted 0.6 mm with hubs fixed (should COLLIDE = trapped)", v_up))
    log.append(("blade 1 pushed 1.0 mm radially outward (should COLLIDE = trapped)", v_rad))
    return log


def bed_fit(items, P):
    bed = P["printer"]["bed"]
    m = P["printer"]["bed_margin"]
    rows = []
    for it in items:
        if not it.printable:
            continue
        s = it.print_pose(it.shape)
        bb = s.bounding_box()
        sz = (bb.size.X, bb.size.Y, bb.size.Z)
        diag_ok = max(sz[0], sz[1]) <= bed[0] - 2 * m and sz[2] <= bed[2]
        rows.append((it.name, sz, bb.min.Z, diag_ok))
    return rows


def roof_clearance(items, P, D):
    """Smallest vertical gap between rotating parts OUTSIDE the throat and the (pitched) roof plane."""
    import numpy as np
    from params import blade_points
    tp = math.tan(math.radians(P["roof_pitch_deg"]))
    gaps = {"lower_hub_rim": D["z_lower_hub_bottom"] - P["lower_hub"]["od"] / 2 * abs(tp)}
    worst = 1e9
    for i in range(P["blade_count"]):
        pts = blade_points(i, P, D)
        worst = min(worst, float((pts[:, 2] - pts[:, 0] * tp).min()))
    gaps["blades"] = worst
    gaps["min"] = min(gaps.values())
    return gaps
