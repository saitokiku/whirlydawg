"""Parametric build123d geometry for every part of the doghouse whirlybird.

All parts are built in ASSEMBLY coordinates (roof surface at axis = Z0, +Z up)
unless the function name says otherwise. `print_pose()` re-orients a part for
the Bambu X1E bed. Units: mm.
"""
from __future__ import annotations

import math

import numpy as np
from build123d import (
    Align, Axis, Box, BuildLine, BuildSketch, Compound, Cylinder, GeomType, Line,
    Location, Mode, Part, Plane, Polyline, Pos, Rectangle, RegularPolygon, Rot,
    Sketch, Spline, Text, ThreePointArc, Vector, extrude, fillet, loft, make_face, mirror, revolve,
    chamfer,
)

from params import blade_frame

RAD = math.pi / 180.0


# ------------------------------------------------------------------ helpers --
def blade_plane(i, P, D, z0) -> Plane:
    """Local frame of blade i: X = chord direction c, Y = -n, Z = +Z, origin at tab centre."""
    T, c, _ = blade_frame(i, P, D)
    return Plane(origin=(T[0], T[1], z0), x_dir=(c[0], c[1], 0), z_dir=(0, 0, 1))


def revolve_profile(pts) -> Part:
    """Revolve a closed (r, z) polygon about the Z axis."""
    with BuildSketch(Plane.XZ) as sk:
        with BuildLine():
            Polyline(*pts, close=True)
        make_face()
    return revolve(sk.sketch, Axis.Z)


def ring(r_in, r_out, z0, z1) -> Part:
    return revolve_profile([(r_in, z0), (r_out, z0), (r_out, z1), (r_in, z1)])


def zcyl(r, z0, z1, x=0.0, y=0.0) -> Part:
    return Pos(x, y, z0) * Cylinder(r, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def radial_box(az_deg, r0, r1, width, z0, z1) -> Part:
    b = Box(r1 - r0, width, z1 - z0, align=(Align.MIN, Align.CENTER, Align.MIN))
    return Rot(0, 0, az_deg) * Pos(r0, 0, z0) * b


def engrave(part: Part, text: str, plane: Plane, size=4.0, depth=0.6) -> Part:
    sk = Text(text, font_size=size)
    tool = plane * extrude(sk, amount=-depth)
    return part - tool


# -------------------------------------------------------------------- blade --
def _cup_xy(Rc, k, R, phi):
    """Blade-local XY (X = chord c, Y = -n) of the point at angle phi on radius R about the cup centre."""
    return (R * math.sin(phi), -k * Rc + k * R * math.cos(phi))


def cup_sector(P, off_in, off_out, s0, s1) -> Sketch:
    """Plan sketch of an annular sector following the blade cup: radii Rc+off_in..Rc+off_out,
    arc-length span s0..s1 (measured on Rc from the tab centre)."""
    B = P["blade"]
    Rc, k = B["cup_radius"], B["cup_direction"]
    f0, f1 = s0 / Rc, s1 / Rc
    fm = 0.5 * (f0 + f1)
    ri, ro = Rc + off_in, Rc + off_out
    with BuildSketch(Plane.XY) as sk:
        with BuildLine():
            ThreePointArc(_cup_xy(Rc, k, ro, f0), _cup_xy(Rc, k, ro, fm), _cup_xy(Rc, k, ro, f1))
            Line(_cup_xy(Rc, k, ro, f1), _cup_xy(Rc, k, ri, f1))
            ThreePointArc(_cup_xy(Rc, k, ri, f1), _cup_xy(Rc, k, ri, fm), _cup_xy(Rc, k, ri, f0))
            Line(_cup_xy(Rc, k, ri, f0), _cup_xy(Rc, k, ro, f0))
        make_face()
    return sk.sketch


def _rounded_corner_rect(x0, x1, z0, z1, corner, r) -> Sketch:
    """Rectangle with one rounded corner; corner = (x, z) of the corner to round."""
    with BuildSketch(Plane.XY) as sk:
        Rectangle(x1 - x0, z1 - z0, align=(Align.MIN, Align.MIN))
        sk_v = [v for v in sk.vertices() if abs(v.X - (corner[0] - x0)) < 1e-6 and abs(v.Y - (corner[1] - z0)) < 1e-6]
        fillet(sk_v, r)
    return Pos(x0, z0) * sk.sketch


def blade_local(P, D) -> Part:
    """One formed blade in its local frame: X = chord c, Y = -n, Z = height above the lower cap face.
    Straight vertically, cupped across the width on cup_radius; tabs follow the same cup."""
    B = P["blade"]
    t, tab, tw = B["thickness"], B["tab_length"], B["tab_width"]
    H = D["cap_separation"]
    u0, u1 = D["blade_u_inner"], D["blade_u_outer"]
    body = Pos(0, 0, -tab) * extrude(cup_sector(P, -t / 2, t / 2, u0, u1), amount=H + 2 * tab)

    # notches either side of each tab, with root radius, plus tab tip chamfers
    r = B["tab_root_radius"]
    cut = None
    for z_sh, z_far, sgn in ((0.0, -tab - 1.0, -1), (H, H + tab + 1.0, +1)):
        lo, hi = (z_far, z_sh) if sgn < 0 else (z_sh, z_far)
        left = _rounded_corner_rect(u0 - 2.0, -tw / 2, lo, hi, (-tw / 2, z_sh), r)
        right = _rounded_corner_rect(tw / 2, u1 + 2.0, lo, hi, (tw / 2, z_sh), r)
        for sk in (left, right):
            tool = extrude(Plane.XZ * sk, amount=12, both=True)
            cut = tool if cut is None else cut + tool
        zt = -tab if sgn < 0 else H + tab
        ch = B["tab_tip_chamfer"]
        for sx in (-1, 1):
            tri = Polyline_face([(sx * tw / 2, zt), (sx * (tw / 2 - ch), zt), (sx * tw / 2, zt - sgn * ch)])
            cut = cut + extrude(Plane.XZ * tri, amount=12, both=True)
    return body - cut


def Polyline_face(pts) -> Sketch:
    with BuildSketch(Plane.XY) as sk:
        with BuildLine():
            Polyline(*pts, close=True)
        make_face()
    return sk.sketch


def blade(i, P, D) -> Part:
    return blade_plane(i, P, D, D["z_lower_face"]) * blade_local(P, D)


# ------------------------------------------------------------------ pockets --
def pocket_tool_local(P, D, extra_depth=0.0) -> Part:
    """Blind pocket following the blade cup, opening at local z=0 and going DOWN (-Z)."""
    K = P["pocket"]
    L, w, dep = D["pocket_length"], K["width"], K["depth"] + extra_depth
    e, sl = K["mouth_end_chamfer"], K["mouth_side_lead_in"]
    wide = cup_sector(P, -(w / 2 + sl), w / 2 + sl, -L / 2 - e, L / 2 + e)
    narrow = cup_sector(P, -w / 2, w / 2, -L / 2, L / 2)
    mouth = loft([wide, Pos(0, 0, -e) * narrow])
    above = extrude(wide, amount=2.0)
    deep = Pos(0, 0, -dep) * extrude(narrow, amount=dep - e)
    return mouth + above + deep


def weep_tool_local(P, D, radial=True) -> Part:
    """Diamond (self-supporting) drain channel from the pocket's outer end, 2 deg fall.
    radial=True points it radially outward in the hub; False points it along local +X (coupons)."""
    K, LH, B = P["pocket"], P["lower_hub"], P["blade"]
    th = B["plan_chord_angle_from_radial"] * RAD
    a = LH["weep_channel_size"]
    half_diag = a * math.sqrt(2) / 2
    ch = Rot(45, 0, 0) * Box(20.0, a, a, align=(Align.MIN, Align.CENTER, Align.CENTER))
    ch = Pos(0, 0, -K["depth"] + half_diag) * ch
    ch = Rot(0, 2.0, 0) * ch                                   # outer end lower
    if radial:
        ch = Rot(0, 0, -th / RAD) * ch                          # radial direction in local frame
    sx, sy = _cup_xy(B["cup_radius"], B["cup_direction"], B["cup_radius"], (D["pocket_length"] / 2 - 1.0) / B["cup_radius"])
    return Pos(sx, sy, 0) * ch


def set_screw_tools(az_deg, z_axis, boss_r, slot_from_z, slot_to_z, F, bore_d) -> Part:
    """Radial M4 tapped-nut set-screw hole + vertical nut slot (opening toward slot_from_z)."""
    hole = Rot(0, 0, az_deg) * Pos(0, 0, z_axis) * Rot(0, 90, 0) * Cylinder(
        F["screw_hole_diameter"] / 2, boss_r + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    x_mid = bore_d / 2 + 1.4 + F["nut_slot_thickness"] / 2
    z0, z1 = sorted((slot_from_z, slot_to_z))
    slot = Box(F["nut_slot_thickness"], F["nut_slot_width"], z1 - z0,
               align=(Align.CENTER, Align.CENTER, Align.MIN))
    slot = Rot(0, 0, az_deg) * Pos(x_mid, 0, z0) * slot
    return hole + slot


SCREW_AZ = 26.0  # azimuth of the lower-hub set screw and the upper-hub captive-nut slot (between ribs/spokes)


# ---------------------------------------------------------------- upper hub --
def upper_hub(P, D) -> Part:
    U, K, F = P["upper_hub"], P["pocket"], P["hub_fixing"]
    zf = D["z_upper_face"]
    R = U["od"] / 2
    T = U["thickness"]
    web = U["center_web_thickness"]
    rb = U["boss_od"] / 2
    ri = U["annulus_inner_radius"]
    ch = U["top_edge_chamfer"]
    lip_w, lip_h = U["drip_lip_width"], U["drip_lip_height"]
    zb = -U["boss_length_below_face"]
    prof = [(0, zb), (rb, zb), (rb, T - web), (ri, T - web), (ri, 0), (R - lip_w, 0),
            (R - lip_w, -lip_h), (R, -lip_h), (R, T - ch), (R - ch, T), (0, T)]
    hub = Pos(0, 0, zf) * revolve_profile(prof)

    # radial ribs under the centre web
    for k in range(U["rib_count"]):
        az = SCREW_AZ + 180.0 / U["rib_count"] + k * 360.0 / U["rib_count"]
        hub += radial_box(az, rb - 1, ri + 1, U["rib_width"], zf + 2.0, zf + T - web + 0.01)

    # blind pockets opening DOWN on the underside face, and drip-lip notches for each blade
    for i in range(P["blade_count"]):
        pl = blade_plane(i, P, D, zf)
        pocket = pl * mirror(pocket_tool_local(P, D), Plane.XY)
        hub -= pocket
        clr = P["blade"]["thickness"] / 2 + U["blade_notch_clearance"]
        notch = extrude(cup_sector(P, -clr, clr, D["blade_u_inner"] - 3.0, D["blade_u_outer"] + 3.0), amount=lip_h + 1.0)
        hub -= pl * Pos(0, 0, -(lip_h + 1.0) + 0.01) * notch

    # shaft blind bore + side-entry slot for the captive M4 nut of the tie rod
    bore_d = P["shaft"]["hub_bore_diameter"]
    hub -= zcyl(bore_d / 2, zf + zb - 1, D["z_upper_bore_top"])
    hub -= Rot(0, 0, SCREW_AZ) * Pos(-4.4, 0, D["z_upper_nut_bottom"] - 0.15) * Box(
        rb + 6.0, F["nut_slot_width"], F["nut_slot_thickness"], align=(Align.MIN, Align.CENTER, Align.MIN))
    # bore entry chamfer
    hub -= Pos(0, 0, zf + zb - 0.01) * Cylinder(bore_d / 2 + 0.8, 0.8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return hub


# ---------------------------------------------------------------- lower hub --
def lower_hub(P, D, solid_variant=False) -> Part:
    L, K, F, S = P["lower_hub"], P["pocket"], P["hub_fixing"], P["stationary"]
    zb = D["z_lower_hub_bottom"]
    T = L["thickness"]
    R = L["od"] / 2
    rci = L["chimney_id"] / 2
    rco = rci + L["chimney_wall"]
    ch = L["top_edge_chamfer"]
    hch = T + L["chimney_height_above_face"]
    if solid_variant:
        body = revolve_profile([(0, 0), (R, 0), (R, T - ch), (R - ch, T), (0, T)])
    else:
        body = revolve_profile([(rci, 0), (R, 0), (R, T - ch), (R - ch, T), (rco, T),
                                (rco, hch - 1.0), (rco - 1.0, hch), (rci, hch)])
    hub = Pos(0, 0, zb) * body

    # central boss with labyrinth cup over the stationary bearing tower
    r_cup = S["tower_od"] / 2 + S["labyrinth_radial_gap"]
    r_cupboss = L["cup_boss_od"] / 2
    rb = L["boss_od"] / 2
    z_ceiling = D["z_cup_ceiling"] - zb
    z_bt = D["z_lower_boss_top"] - zb
    boss = Pos(0, 0, zb) * revolve_profile([
        (r_cup, 0), (r_cupboss, 0), (r_cupboss, L["spoke_height"]), (rb, L["spoke_height"] + 3),
        (rb, z_bt), (0, z_bt), (0, z_ceiling), (r_cup, z_ceiling)])
    hub += boss
    if not solid_variant:
        for k in range(L["spoke_count"]):
            az = SCREW_AZ + 45.0 + k * 360.0 / L["spoke_count"]
            hub += radial_box(az, r_cupboss - 1.0, rci + 1.0, L["spoke_width"], zb, zb + L["spoke_height"])

    # blind pockets opening UP + concealed weep channels
    for i in range(P["blade_count"]):
        pl = blade_plane(i, P, D, D["z_lower_face"])
        hub -= pl * pocket_tool_local(P, D)
        hub -= pl * weep_tool_local(P, D)

    bore_d = P["shaft"]["hub_bore_diameter"]
    hub -= zcyl(bore_d / 2, D["z_cup_ceiling"] - 1, D["z_lower_boss_top"] + 1)
    hub -= set_screw_tools(SCREW_AZ, D["z_lower_set_screw"], rb, D["z_lower_boss_top"] + 1,
                           D["z_lower_set_screw"] - 4.5, F, bore_d)
    hub -= Pos(0, 0, D["z_lower_boss_top"] - 0.8) * Cylinder(bore_d / 2 + 0.8, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return hub


# ------------------------------------------------------- stationary support --
def bearing_support(P, D) -> Part:
    S, BR = P["stationary"], P["bearings"]
    zt = D["z_collar_top"]
    zr0 = D["z_support_ring_bottom"]
    ri = S["throat_id"] / 2
    ro = ri + S["support_ring_wall"]
    rt = S["tower_od"] / 2
    part = ring(ri, ro, zr0, zt)
    part += zcyl(rt, D["z_tower_bottom"], D["z_tower_top"])
    for k in range(S["support_spoke_count"]):
        az = 90.0 + k * 360.0 / S["support_spoke_count"]
        part += radial_box(az, rt - 1.0, ri + 1.0, S["support_spoke_width"], zr0, zt)
        # tapered gusset under each spoke towards the tower (stiffens the cantilevered tower)
        g = Polyline_face([(rt - 1.0, zr0), (rt + 22.0, zr0), (rt - 1.0, zr0 - 22.0)])
        g = extrude(Plane.XZ * g, amount=S["support_spoke_width"] / 2, both=True)
        part += Rot(0, 0, az) * g
        part += radial_box(az, ri - 4.0, ri + 0.5, 10.0, zr0, zt)            # screw boss
        hole = Rot(0, 0, az) * Pos(ri - 6.0, 0, zt - S["support_ring_height"] / 2) * Rot(0, 90, 0) * \
            Cylinder(1.3, 12.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        part -= hole

    seat = BR["seat_bore_diameter"] / 2
    part -= zcyl(seat, D["z_tower_top"] - BR["width"], D["z_tower_top"] + 1)
    part -= zcyl(seat, D["z_tower_bottom"] - 1, D["z_tower_bottom"] + BR["width"])
    part -= zcyl(5.5, D["z_tower_bottom"], D["z_tower_top"])
    for z, up in ((D["z_tower_top"], True), (D["z_tower_bottom"], False)):
        c = Pos(0, 0, z) * Cylinder(seat + 0.5, 0.5, align=(Align.CENTER, Align.CENTER, Align.MAX if up else Align.MIN))
        part -= c
    return part


def support_ring_outer_radius(P):
    S = P["stationary"]
    return S["throat_id"] / 2 + S["support_ring_wall"]


# ------------------------------------------------------------ roof adapter --
def roof_adapter(P, D) -> Part:
    S = P["stationary"]
    p = P["roof_pitch_deg"] * RAD
    tp = math.tan(p)
    zt = D["z_collar_top"]
    ri = S["throat_id"] / 2
    rcb = support_ring_outer_radius(P) + 0.25
    ro = rcb + S["collar_wall"]
    rf = S["flange_od"] / 2
    roof = Plane(origin=(0, 0, 0), x_dir=(math.cos(p), 0, math.sin(p)), z_dir=(-math.sin(p), 0, math.cos(p)))
    big = 2 * rf + 40
    # flange slab normal to roof
    flange = roof * Box(big, big, S["flange_thickness"], align=(Align.CENTER, Align.CENTER, Align.MIN))
    flange = flange & zcyl(rf, -rf * tp - 20, rf * tp + 40)
    collar = zcyl(ro, -rf * tp - 20, zt)
    above_roof = roof * Box(big, big, 400, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part = (flange + (collar & above_roof))
    # outer top chamfer of collar
    part -= revolve_profile([(ro - 1.5, zt + 0.01), (ro + 0.01, zt + 0.01), (ro + 0.01, zt - 1.5)])
    part -= zcyl(ri, -rf * tp - 30, zt + 1)                                # throat
    part -= zcyl(rcb, D["z_support_ring_bottom"], zt + 1)                 # counterbore for support ring
    # gasket groove on the roof-contact face
    g = S["gasket_groove_radius"]
    groove = roof * Pos(0, 0, -1) * (Cylinder(g + S["gasket_groove_width"] / 2, S["gasket_groove_depth"] + 1,
                                              align=(Align.CENTER, Align.CENTER, Align.MIN)) -
                                     Cylinder(g - S["gasket_groove_width"] / 2, S["gasket_groove_depth"] + 1,
                                              align=(Align.CENTER, Align.CENTER, Align.MIN)))
    part -= groove
    # roof screws (normal to roof)
    for k in range(S["flange_screw_count"]):
        a = (k + 0.5) * 2 * math.pi / S["flange_screw_count"]
        x, y = S["flange_screw_circle"] / 2 * math.cos(a), S["flange_screw_circle"] / 2 * math.sin(a)
        part -= roof * Pos(x, y, -5) * Cylinder(
            S["flange_screw_hole"] / 2, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # radial clearance holes for the 3 support screws
    for k in range(S["support_spoke_count"]):
        az = 90.0 + k * 360.0 / S["support_spoke_count"]
        part -= Rot(0, 0, az) * Pos(rcb - 1.0, 0, zt - S["support_ring_height"] / 2) * Rot(0, 90, 0) * \
            Cylinder(1.7, S["collar_wall"] + 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return part


# ---------------------------------------------------------------- rain tray --
def rain_tray(P, D) -> Part:
    RT, S = P["rain_tray"], P["stationary"]
    zf = D["z_tower_bottom"] - RT["drop_below_tower"]
    R = RT["od"] / 2
    w = RT["wall"]
    rt = S["tower_od"] / 2 + 0.25
    grip_top = D["z_tower_bottom"] + 10.0
    part = revolve_profile([(rt, zf), (R, zf), (R, zf + RT["rim_height"]), (R - w, zf + RT["rim_height"]),
                            (R - w, zf + w), (rt + 2.25, zf + w), (rt + 2.25, grip_top), (rt, grip_top)])
    for k in range(3):
        g = Polyline_face([(rt + 2.0, zf + w - 0.1), (rt + 30.0, zf + w - 0.1), (rt + 2.0, grip_top - 12.0)])
        part += Rot(0, 0, 60 + k * 120) * extrude(Plane.XZ * g, amount=1.5, both=True)
    # clamp-screw rib on the standpipe, standing on the floor so it prints without support
    part += radial_box(0, rt + 1.0, rt + 7.0, 9.0, zf + w - 0.1, grip_top)
    part -= Pos(0, 0, grip_top - 4.5) * Rot(0, 90, 0) * Cylinder(1.3, 40, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # drain hole (press in a 1/4 in OD vinyl tube with silicone, or plug it); no spout so the floor prints flat
    part -= zcyl(RT["drain_spout_od"] / 2, zf - 1.0, zf + w + 1, x=R - 10.0)
    return part


# --------------------------------------------------------- purchased parts --
def shaft(P, D) -> Part:
    """Hollow 1/4 in stainless tube shaft (the tie rod runs inside it)."""
    return ring(P["shaft"]["tube_id"] / 2, P["shaft"]["nominal_diameter"] / 2, D["z_shaft_bottom"], D["z_shaft_top"])


def _hex_nut(z0, height, af=7.0, hole=2.0):
    return Pos(0, 0, z0) * extrude(RegularPolygon(af / math.sqrt(3), 6) - RegularPolygon(hole, 24), amount=height)


def tie_rod_parts(P, D):
    """M4 tie rod, captive nut in the upper hub, washer + nyloc nut under the shaft."""
    F = P["hub_fixing"]
    rod = zcyl(F["tie_rod_diameter"] / 2, D["z_tie_rod_bottom"], D["z_tie_rod_top"])
    top_nut = Rot(0, 0, SCREW_AZ) * _hex_nut(D["z_upper_nut_bottom"], 3.2)
    washer = ring(2.15, 4.5, D["z_shaft_bottom"] - 1.2, D["z_shaft_bottom"])
    bot_nut = Rot(0, 0, SCREW_AZ) * _hex_nut(D["z_shaft_bottom"] - 1.2 - 5.0, 5.0)
    return rod, top_nut, washer, bot_nut


def bearing(P, z_center) -> list[Part]:
    BR = P["bearings"]
    w = BR["width"]
    z0, z1 = z_center - w / 2, z_center + w / 2
    inner = ring(BR["id"] / 2, BR["inner_race_land_od"] / 2, z0, z1)
    outer = ring(BR["od"] / 2 - 1.2, BR["od"] / 2, z0, z1)
    seal = ring(BR["inner_race_land_od"] / 2 + 0.15, BR["od"] / 2 - 1.2, z0 + 0.3, z1 - 0.3)
    return [inner, outer, seal]


def washers(P, D) -> list[Part]:
    S, BR = P["stationary"], P["bearings"]
    ro, ri = BR["inner_race_land_od"] / 2, 3.25
    top = ring(ri, ro, D["z_upper_bearing_top"], D["z_cup_ceiling"])
    bot = ring(ri, ro, D["z_washer_bottom_bottom"], D["z_tower_bottom"])
    return [top, bot]


def shaft_collar(P, D) -> Part:
    S = P["stationary"]
    return ring(P["shaft"]["nominal_diameter"] / 2, S["shaft_collar_od"] / 2, D["z_collar_bottom_face"], D["z_collar_top_face"])


def nut_and_screw(P, D, z_axis, upper: bool):
    F = P["hub_fixing"]
    bore_d = P["shaft"]["hub_bore_diameter"]
    x_mid = bore_d / 2 + 1.4 + F["nut_slot_thickness"] / 2
    nut = RegularPolygon(7.0 / math.sqrt(3), 6)
    nut = Rot(0, 0, SCREW_AZ) * Pos(x_mid, 0, z_axis) * Rot(0, 90, 0) * extrude(
        nut - RegularPolygon(2.0, 24), amount=3.2 / 2, both=True)
    screw = Rot(0, 0, SCREW_AZ) * Pos(P["shaft"]["nominal_diameter"] / 2, 0, z_axis) * Rot(0, 90, 0) * \
        Cylinder(1.95, 6.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return nut, screw


# ---------------------------------------------------------------- inlet vent --
def inlet_louver(P) -> Part:
    W, H, T = 170.0, 120.0, 3.0
    ow, oh, depth = 140.0, 90.0, 15.0
    plate = Box(W, H, T, align=(Align.CENTER, Align.CENTER, Align.MIN))
    frame = Box(ow + 4, oh + 4, depth, align=(Align.CENTER, Align.CENTER, Align.MIN)) - \
        Box(ow, oh, depth + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part = plate + frame
    part -= Box(ow, oh, T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # 45 degree rain louvres (slats run along X, shed water outward/downward)
    pitch = 12.0
    n = int(oh // pitch)
    for k in range(n + 1):
        y = -oh / 2 + k * pitch
        slat = Box(ow + 1, 2.0, depth * 1.414, align=(Align.CENTER, Align.CENTER, Align.MIN))
        slat = Pos(0, y, 0) * Rot(45, 0, 0) * slat
        part += slat & Box(ow + 1, oh, depth, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # insect-screen recess on the wall side (Z=0 face)
    part -= Box(ow + 10, oh + 10, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sx in (-1, 1):
        for sy in (-1, 1):
            part -= zcyl(2.25, -1, T + 1, sx * (W / 2 - 8), sy * (H / 2 - 8))
    return part


# -------------------------------------------------------------- forming die --
def forming_dies(P, D):
    """Cylindrical press die that rolls the blade ACROSS its width onto the cup radius.
    X = along the blade length, Y = across the width, Z up. Lower die is convex, upper concave.
    The die radius is tighter than the cup radius by the springback factor."""
    B, FD = P["blade"], P["forming_die"]
    t, tab, tw = B["thickness"], B["tab_length"], B["tab_width"]
    H = D["cap_separation"]
    Rd = B["cup_radius"] / FD["springback_factor"]          # mid-surface radius while clamped
    base = FD["base_thickness"]
    L = H + 2 * tab + 2 * FD["wall"]
    x0 = -tab - FD["wall"]
    half_ang = (B["body_chord"] / 2 + 4.0) / Rd
    Wd = 2 * (Rd - t / 2) * math.sin(half_ang)
    axis_z = -Rd                                               # cylinder axis (blank crest at Z = 0)
    cyl = lambda r: Pos(x0 - 1, 0, axis_z) * Rot(0, 90, 0) * Cylinder(r, L + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))  # noqa: E731
    z_edge_lo = axis_z + math.sqrt((Rd - t / 2) ** 2 - (Wd / 2) ** 2)
    lower = Pos(x0, 0, z_edge_lo - base) * Box(L, Wd, base - z_edge_lo + 1.0, align=(Align.MIN, Align.CENTER, Align.MIN))
    lower = lower & cyl(Rd - t / 2)                          # convex top on the forming radius
    # locating posts in the notch zones beside each tab (shoulders butt against them)
    post_y = tw / 2 + 0.3 + 2.0
    posts = None
    for xa, xb in ((-tab + 1.0, -0.3), (H + 0.3, H + tab - 1.0)):
        for sy in (-1, 1):
            pz = axis_z + math.sqrt((Rd - t / 2) ** 2 - post_y ** 2)
            pst = Pos(xa, sy * post_y, pz - 3.0) * Box(xb - xa, 4.0, 3.0 + t + 2.5, align=(Align.MIN, Align.CENTER, Align.MIN))
            posts = pst if posts is None else posts + pst
    lower = lower + posts
    z_edge_up = axis_z + math.sqrt((Rd + t / 2) ** 2 - (Wd / 2) ** 2)
    upper = Pos(x0, 0, z_edge_up) * Box(L, Wd, t + base + (0 - z_edge_up) + 2.0, align=(Align.MIN, Align.CENTER, Align.MIN))
    upper = upper - cyl(Rd + t / 2)
    upper = upper - _grow(posts, 0.6)                        # relief over the locating posts
    return lower, upper, Rd, H


def _grow(shape, d):
    """Relief clearance around the locating posts (bounding boxes grown by d)."""
    out = None
    for so in shape.solids():
        bb = so.bounding_box()
        b = Pos(bb.min.X - d, bb.min.Y - d, bb.min.Z - d) * Box(bb.size.X + 2 * d, bb.size.Y + 2 * d, bb.size.Z + 2 * d + 30,
                                                               align=(Align.MIN, Align.MIN, Align.MIN))
        out = b if out is None else out + b
    return out


# ------------------------------------------------------------------ coupons --
def socket_coupon(P, D, which: str) -> Part:
    """Single representative blind pocket. which = 'top' (opens down) or 'bottom' (opens up, with weep)."""
    K = P["pocket"]
    T = P["upper_hub"]["thickness"] if which == "top" else P["lower_hub"]["thickness"]
    xr = D["pocket_length"] / 2 + D["upper_hub_shell_outside_pocket"]
    block = Box(xr + 16.0, 22.0, T, align=(Align.MAX, Align.CENTER, Align.MAX))
    block = Pos(xr, 0, 0) * block
    tool = pocket_tool_local(P, D)
    part = block - tool
    if which == "bottom":
        part -= weep_tool_local(P, D, radial=False)
    label = f"{'T' if which == 'top' else 'B'} {K['width']:.2f}"
    part = engrave(part, label, Plane(origin=(-11.0, -7.0, 0), x_dir=(1, 0, 0), z_dir=(0, 0, 1)), size=3.5)
    if which == "top":
        part = mirror(part, Plane.XY)   # assembly-like orientation: opening faces down
    return part


def slot_width_coupon(P, D, widths=(1.85, 1.95, 2.05, 2.15)) -> Part:
    T = P["lower_hub"]["thickness"]
    pitch = 24.0
    n = len(widths)
    part = Box(pitch * n + 6, 34.0, T, align=(Align.MIN, Align.CENTER, Align.MAX))
    for k, w in enumerate(widths):
        Q = {**P, "pocket": {**P["pocket"], "width": w}}
        x = 3 + pitch * (k + 0.5)
        part -= Pos(x, 0, 0) * Rot(0, 0, 90) * pocket_tool_local(Q, D)
        part = engrave(part, f"{w:.2f}", Plane(origin=(x - 5.5, -15.5, 0), x_dir=(1, 0, 0), z_dir=(0, 0, 1)), size=3.5)
    return part


def fit_coupon(P) -> Part:
    seats = (15.80, 15.90, 16.00, 16.10)
    bores = (6.45, 6.55, 6.65)
    w = P["bearings"]["width"]
    plate = Box(100.0, 50.0, w + 1.5, align=(Align.MIN, Align.MIN, Align.MIN))
    part = plate
    for k, d in enumerate(seats):
        x = 13 + 24.5 * k
        part -= zcyl(d / 2, 1.5, w + 2.0, x, 15)
        part -= zcyl(4.5, -1, 3, x, 15)
        part = engrave(part, f"{d:.2f}", Plane(origin=(x - 7, 2.5, w + 1.5), x_dir=(1, 0, 0), z_dir=(0, 0, 1)), size=3.2)
    for k, d in enumerate(bores):
        x = 20 + 30 * k
        part += zcyl(7.0, 0, 20.0, x, 38)
        part -= zcyl(d / 2, -1, 21.0, x, 38)
        part = engrave(part, f"{d:.2f}", Plane(origin=(x + 7.5, 33.5, w + 1.5), x_dir=(1, 0, 0), z_dir=(0, 0, 1)), size=3.0)
    return part


def drill_guide(P) -> Part:
    bore = P["shaft"]["hub_bore_diameter"]
    part = Box(40.0, 24.0, 22.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part -= Pos(0, 0, 9.0) * Rot(0, 90, 0) * Cylinder(bore / 2, 50)
    part -= zcyl(1.8, 9.0, 23.0)
    part -= Pos(0, 0, 9.0) * Box(42, 1.2, 18, align=(Align.CENTER, Align.CENTER, Align.MAX))  # flex slot for clamping
    part = engrave(part, "SPOT 3.5", Plane(origin=(-17, -10.5, 22.0), x_dir=(1, 0, 0), z_dir=(0, 0, 1)), size=3.5)
    return part


def thrust_washer(P, thickness) -> Part:
    return ring(3.25, P["bearings"]["inner_race_land_od"] / 2, 0, thickness)
