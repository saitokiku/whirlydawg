"""Blade flat pattern (developed blank) as exact lines + arcs, plus DXF / SVG writers.

Template coordinates: x across the blade width (0 = INNER edge, toward the shaft),
y along the blade length (0 = tip of the LOWER tab). Units mm.
"""
from __future__ import annotations

import math

import ezdxf
import numpy as np

from params import bow_offset, bow_slope

OUTER_CORNER_R = 2.0   # deburr radius on the 4 outer body corners (template only; not in 3-D model)


def outline(P, D):
    """Closed outline as list of ('L', p0, p1) and ('A', centre, r, a0_deg, a1_deg, p0, p1) (CCW arcs)."""
    B = P["blade"]
    W, Lb, tl, tw = B["body_chord"], B["blank_length"], B["tab_length"], B["tab_width"]
    m, r, ch = B["tab_inner_margin"], B["tab_root_radius"], B["tab_tip_chamfer"]
    rc = OUTER_CORNER_R
    xa, xb = m, m + tw            # tab edges
    y1, y2 = tl, Lb - tl          # shoulder lines
    segs = []

    def L(p, q):
        segs.append(("L", p, q))

    def A(c, rad, a0, a1):
        p0 = (c[0] + rad * math.cos(math.radians(a0)), c[1] + rad * math.sin(math.radians(a0)))
        p1 = (c[0] + rad * math.cos(math.radians(a1)), c[1] + rad * math.sin(math.radians(a1)))
        segs.append(("A", c, rad, a0, a1, p0, p1))

    # walk CCW starting at bottom tab tip, left chamfer end
    L((xa + ch, 0), (xb - ch, 0))
    L((xb - ch, 0), (xb, ch))
    L((xb, ch), (xb, y1 - r))
    A((xb + r, y1 - r), r, 180, 90)          # root fillet (clockwise in material = arc drawn 180->90)
    L((xb + r, y1), (W - rc, y1))
    A((W - rc, y1 + rc), rc, 270, 360)       # outer-bottom corner
    L((W, y1 + rc), (W, y2 - rc))
    A((W - rc, y2 - rc), rc, 0, 90)
    L((W - rc, y2), (xb + r, y2))
    A((xb + r, y2 + r), r, 270, 180)
    L((xb, y2 + r), (xb, Lb - ch))
    L((xb, Lb - ch), (xb - ch, Lb))
    L((xb - ch, Lb), (xa + ch, Lb))
    L((xa + ch, Lb), (xa, Lb - ch))
    L((xa, Lb - ch), (xa, y2 + r))
    A((xa - r, y2 + r), r, 0, -90)
    L((xa - r, y2), (rc, y2))
    A((rc, y2 - rc), rc, 90, 180)
    L((0, y2 - rc), (0, y1 + rc))
    A((rc, y1 + rc), rc, 180, 270)
    L((rc, y1), (xa - r, y1))
    A((xa - r, y1 - r), r, 90, 0)
    L((xa, y1 - r), (xa, ch))
    L((xa, ch), (xa + ch, 0))
    return segs


def polyline_points(segs, step_deg=5):
    pts = []
    for s in segs:
        if s[0] == "L":
            pts.append(s[1])
        else:
            _, c, r, a0, a1, p0, p1 = s
            n = max(2, int(abs(a1 - a0) / step_deg) + 1)
            for a in np.linspace(a0, a1, n)[:-1]:
                pts.append((c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a))))
    return pts


def annotations(P, D):
    B = P["blade"]
    W, Lb, tl, tw, m = B["body_chord"], B["blank_length"], B["tab_length"], B["tab_width"], B["tab_inner_margin"]
    return {
        "tab_centerline_x": m + tw / 2,
        "body_centerline_x": W / 2,
        "shoulder_y": (tl, Lb - tl),
        "bow_peak_y": tl + D["blade_developed_body_length"] / 2,
        "W": W, "L": Lb,
    }


def write_dxf(P, D, path, layout="single"):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for name, col, lt in (("CUT", 7, "CONTINUOUS"), ("CENTER", 1, "CENTER"), ("SHOULDER", 3, "DASHED"),
                          ("STOCK", 8, "PHANTOM"), ("NOTES", 2, "CONTINUOUS")):
        doc.layers.add(name, color=col, linetype=lt)
    msp = doc.modelspace()
    segs = outline(P, D)
    an = annotations(P, D)
    B = P["blade"]

    def place(ox, oy, rot90=False, label=""):
        def T(p):
            x, y = p
            return (ox + y, oy + x) if rot90 else (ox + x, oy + y)
        for s in segs:
            if s[0] == "L":
                msp.add_line(T(s[1]), T(s[2]), dxfattribs={"layer": "CUT"})
            else:
                _, c, r, a0, a1, p0, p1 = s
                # ezdxf arcs are CCW from start to end; normalise
                if rot90:
                    # mirror about y=x swaps orientation: angle a -> 90 - a
                    b0, b1 = 90 - a1, 90 - a0
                    cc = T(c)
                else:
                    b0, b1, cc = a0, a1, T(c)
                lo, hi = (b0, b1) if b1 > b0 else (b1, b0)
                msp.add_arc(cc, r, lo % 360, hi % 360, dxfattribs={"layer": "CUT"})
        xt = an["tab_centerline_x"]
        msp.add_line(T((xt, -3)), T((xt, an["L"] + 3)), dxfattribs={"layer": "CENTER"})
        for ys in an["shoulder_y"]:
            msp.add_line(T((-2, ys)), T((an["W"] + 2, ys)), dxfattribs={"layer": "SHOULDER"})
        yb = an["bow_peak_y"]
        msp.add_line(T((-2, yb)), T((an["W"] + 2, yb)), dxfattribs={"layer": "CENTER"})
        if label:
            msp.add_text(label, height=3.5, dxfattribs={"layer": "NOTES"}).set_placement(T((an["W"] / 2 - 8, an["L"] / 2 + 20)))

    if layout == "single":
        place(0, 0, label="BLADE x1 TEST")
        msp.add_text(f"1.6 mm Al. Blank {B['body_chord']:.2f} x {B['blank_length']:.1f}. Tabs {B['tab_width']:.0f} x {B['tab_length']:.0f}. "
                     f"Cut OUTSIDE the line (kerf). Root R{B['tab_root_radius']:.0f}.", height=2.5,
                     dxfattribs={"layer": "NOTES"}).set_placement((0, -10))
    else:
        sl, sw = 298.45, 95.25      # 11.75 x 3.75 in stock
        kerf = 3.0
        n = 0
        for k in range(4):
            oy = k * (sw + 15)
            msp.add_lwpolyline([(0, oy), (sl, oy), (sl, oy + sw), (0, oy + sw)], close=True, dxfattribs={"layer": "STOCK"})
            msp.add_text(f"STOCK {k + 1}: 11.75 x 3.75 in (298.45 x 95.25)", height=3, dxfattribs={"layer": "NOTES"}).set_placement((0, oy + sw + 3))
            for j in range(2):
                n += 1
                ox = 4.0 + j * (B["blank_length"] + kerf)
                place(ox, oy + 4.0, rot90=True, label=f"BLADE {n}")
    doc.saveas(path)
    return path


def svg_blade(P, D, path, with_profile=True):
    """1:1 SVG (mm user units) of the flat blank + formed side profile."""
    segs = outline(P, D)
    an = annotations(P, D)
    B = P["blade"]
    margin = 15
    W, L = an["W"], an["L"]
    prof_w = 45 if with_profile else 0
    width, height = W + 2 * margin + prof_w, L + 2 * margin + 20

    def tx(x):
        return margin + x

    def ty(y):
        return margin + 10 + (L - y)

    d = []
    for s in segs:
        if s[0] == "L":
            if not d:
                d.append(f"M {tx(s[1][0]):.3f} {ty(s[1][1]):.3f}")
            d.append(f"L {tx(s[2][0]):.3f} {ty(s[2][1]):.3f}")
        else:
            _, c, r, a0, a1, p0, p1 = s
            sweep = 1 if a1 > a0 else 0     # y is flipped in SVG
            d.append(f"A {r:.3f} {r:.3f} 0 0 {sweep} {tx(p1[0]):.3f} {ty(p1[1]):.3f}")
    d.append("Z")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}mm" height="{height:.2f}mm" viewBox="0 0 {width:.2f} {height:.2f}">',
           f'<rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" fill="white"/>',
           f'<path d="{" ".join(d)}" fill="none" stroke="black" stroke-width="0.25"/>']
    xt = an["tab_centerline_x"]
    out.append(f'<line x1="{tx(xt)}" y1="{ty(-3)}" x2="{tx(xt)}" y2="{ty(L + 3)}" stroke="red" stroke-width="0.15" stroke-dasharray="4 1 1 1"/>')
    for ys in an["shoulder_y"]:
        out.append(f'<line x1="{tx(-3)}" y1="{ty(ys)}" x2="{tx(W + 3)}" y2="{ty(ys)}" stroke="green" stroke-width="0.15" stroke-dasharray="2 1"/>')
    out.append(f'<text x="{tx(0)}" y="{margin}" font-size="3" font-family="sans-serif">BLADE BLANK 1:1 - print at 100% - check 50 mm bar</text>')
    out.append(f'<line x1="{tx(0)}" y1="{height - 6}" x2="{tx(50)}" y2="{height - 6}" stroke="black" stroke-width="0.4"/>')
    out.append(f'<text x="{tx(0)}" y="{height - 8}" font-size="2.5" font-family="sans-serif">50 mm</text>')
    if with_profile:
        H, s, t = D["cap_separation"], B["bow_sagitta"], B["thickness"]
        z = np.linspace(0, H, 121)
        w = bow_offset(z, s, H)
        x0 = tx(W) + 15
        tl = B["tab_length"]

        def py(zv):
            return ty(zv + tl)
        pts = " ".join(f"{x0 + wv:.3f},{py(zv):.3f}" for wv, zv in zip(w, z))
        out.append(f'<polyline points="{x0},{py(-tl)} {pts} {x0},{py(H + tl)}" fill="none" stroke="blue" stroke-width="0.3"/>')
        out.append(f'<line x1="{x0}" y1="{py(-tl)}" x2="{x0}" y2="{py(H + tl)}" stroke="gray" stroke-width="0.15" stroke-dasharray="2 1"/>')
        out.append(f'<text x="{x0 - 2}" y="{py(H + tl) - 3}" font-size="2.5" font-family="sans-serif">FORMED SIDE PROFILE</text>')
        out.append(f'<text x="{x0 + s + 1}" y="{py(H / 2)}" font-size="2.5" font-family="sans-serif">{s:.0f} mm bow</text>')
    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))
    return path
