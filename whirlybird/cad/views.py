"""All CAD renders used by the drawings and the README (true tessellated CAD, not illustrations)."""
from __future__ import annotations

import math

from build123d import Keep, Plane, Pos, split

import geometry as g
import render as R
from params import blade_frame, derive, variant

ROT_COLORS = {"rotating": (0.93, 0.50, 0.15), "purchased-rotating": (0.85, 0.30, 0.10),
              "stationary": (0.35, 0.50, 0.75), "purchased-stationary": (0.20, 0.35, 0.65)}


def _cut(items, plane, keep=Keep.BOTTOM):
    out = []
    for it in items:
        try:
            s = split(it.shape, plane, keep=keep)
        except Exception:
            continue
        if s is not None and s.volume > 1e-6:
            out.append((s, it))
    return out


def make_all(P, D, items, outdir, extras=None):
    outdir.mkdir(parents=True, exist_ok=True)
    full = [(it.shape, it.color, 1.0) for it in items]
    R.render(full, outdir / "assembly_iso.png", "iso", zoom=1.15)
    R.render(full, outdir / "assembly_iso_from_below.png", "iso_low", zoom=1.15)
    R.render(full, outdir / "view_top.png", "top", zoom=1.1)
    R.render(full, outdir / "view_side.png", "front", zoom=1.1)
    R.render(full, outdir / "view_underside.png", "bottom", zoom=1.1)

    # half section through the axis (keeps +Y half, looks from -Y)
    sec = _cut(items, Plane.XZ)
    R.render([(s, it.color, 1.0) for s, it in sec], outdir / "section_axial.png", "front", zoom=1.1)
    R.render([(s, it.color, 1.0) for s, it in sec], outdir / "section_axial_iso.png", "section", zoom=1.2)
    R.render([(s, it.color, 1.0) for s, it in sec], outdir / "section_bearing_detail.png", "front", zoom=3.2,
             focus=(0, 0, 5))

    # blind pocket detail: vertical plane along blade-1 chord through the tab centre
    T, c, n = blade_frame(0, P, D)
    pp = Plane(origin=(T[0], T[1], 0), x_dir=(c[0], c[1], 0), z_dir=(n[0], n[1], 0))
    pk = _cut([it for it in items if it.name in ("upper_hub_closed_top", "lower_hub_closed_bottom", "blade_1")], pp, Keep.TOP)
    view = ((-n[0], -n[1], 0.0), (0, 0, 1))    # look at the cut face from the removed side
    for tag, zc in (("upper", D["z_upper_face"] + 2), ("lower", D["z_lower_face"] - 2)):
        R.render([(s, it.color, 1.0) for s, it in pk], outdir / f"pocket_section_{tag}.png", view, ortho=True,
                 zoom=5.0, focus=(T[0] + 8 * c[0], T[1] + 8 * c[1], zc))

    # rotor vs stationary colour map + separated
    rs = [(it.shape, ROT_COLORS[it.role], 1.0) for it in items]
    R.render(rs, outdir / "rotor_vs_stationary.png", "iso", zoom=1.15,
             title="ORANGE = rotates with shaft     BLUE = fixed to roof")
    rs_sec = [(s, ROT_COLORS[it.role], 1.0) for s, it in sec]
    R.render(rs_sec, outdir / "rotor_vs_stationary_section.png", "front", zoom=1.1,
             title="SECTION  -  ORANGE rotating  /  BLUE stationary")
    sep = [(Pos(0, 0, 70) * it.shape if "rotating" in it.role else it.shape, ROT_COLORS[it.role], 1.0) for it in items]
    R.render(sep, outdir / "rotor_lifted_off_stationary.png", "iso", zoom=1.1,
             title="Rotor (orange) lifted 70 mm off the stationary support (blue)")

    # exploded
    ex = [(Pos(0, 0, it.explode * 1.6) * it.shape, it.color, 1.0) for it in items]
    R.render(ex, outdir / "assembly_exploded.png", "iso", size=(1400, 1800), zoom=1.05)
    R.render(ex, outdir / "assembly_exploded_side.png", "front", size=(1400, 1800), zoom=1.05)

    # hubs: show blind pockets and closed faces
    uh = next(it.shape for it in items if it.name == "upper_hub_closed_top")
    lh = next(it.shape for it in items if it.name == "lower_hub_closed_bottom")
    R.render([(uh, "rotor", 1.0)], outdir / "upper_hub_top_closed.png", "iso", zoom=1.2)
    R.render([(uh, "rotor", 1.0)], outdir / "upper_hub_underside_blind_pockets.png", "iso_low", zoom=1.2)
    R.render([(uh, "rotor", 1.0)], outdir / "upper_hub_underside_plan.png", "bottom", zoom=1.15)
    R.render([(lh, "rotor", 1.0)], outdir / "lower_hub_top_blind_pockets.png", "iso", zoom=1.2)
    R.render([(lh, "rotor", 1.0)], outdir / "lower_hub_bottom_closed.png", "iso_low", zoom=1.2)
    R.render([(lh, "rotor", 1.0)], outdir / "lower_hub_top_plan.png", "top", zoom=1.15)
    for it in items:
        if it.name in ("bearing_support_stationary", "roof_flash_adapter", "rain_baffle_if_needed"):
            R.render([(it.shape, it.color, 1.0)], outdir / f"{it.name}.png", "iso", zoom=1.2)
    b1 = next(it.shape for it in items if it.name == "blade_1")
    R.render([(b1, "blade", 1.0)], outdir / "blade_formed.png", "iso", zoom=1.3)

    if extras:
        for name in ("blade_forming_die_lower", "blade_forming_die_upper", "single_blade_socket_test_top",
                     "single_blade_socket_test_bottom", "slot_clearance_coupon_1p85_1p95_2p05_2p15",
                     "bearing_and_shaft_fit_coupon", "shaft_dimple_drill_guide", "inlet_vent_louver"):
            shape, pose = extras[name]
            R.render([(pose(shape), "tool" if "die" in name or "guide" in name else "rotor", 1.0)],
                     outdir / f"print_{name}.png", "iso", size=(1000, 800), zoom=1.2)
        lo, up = extras["blade_forming_die_lower"][0], extras["blade_forming_die_upper"][0]
        R.render([(lo, "tool", 1.0), (Pos(0, 0, 45) * up, (0.75, 0.6, 0.9), 1.0)], outdir / "forming_die_open.png",
                 "iso", size=(1200, 900), zoom=1.2)
    for it in items:
        if it.printable:
            R.render([(it.print_pose(it.shape), it.color, 1.0)], outdir / f"print_{it.name}.png", "iso",
                     size=(1000, 800), zoom=1.2)

    # 8 / 10 / 12 comparison (same blade envelope, real CAD)
    for nbl in (8, 10, 12):
        Q = variant(P, blade_count=nbl)
        DQ = derive(Q)
        parts = [(g.upper_hub(Q, DQ), "rotor", 1.0), (g.lower_hub(Q, DQ), "rotor", 1.0)]
        parts += [(g.blade(i, Q, DQ), "blade", 1.0) for i in range(nbl)]
        R.render(parts, outdir / f"compare_{nbl}_blades_iso.png", "iso", size=(900, 800), zoom=1.15, title=f"{nbl} blades")
        R.render(parts[1:], outdir / f"compare_{nbl}_blades_top_no_cap.png", "top", size=(900, 800), zoom=1.1,
                 title=f"{nbl} blades (upper hub hidden)")
    # chord-angle variants (plan view, upper hub hidden)
    for th in (25, 35, 45):
        Q = variant(P, **{"blade.plan_chord_angle_from_radial": th})
        DQ = derive(Q)
        parts = [(g.lower_hub(Q, DQ), "rotor", 1.0)] + [(g.blade(i, Q, DQ), "blade", 1.0) for i in range(Q["blade_count"])]
        R.render(parts, outdir / f"compare_chord_{th}deg_top.png", "top", size=(900, 800), zoom=1.1,
                 title=f"chord angle {th} deg from radial")
