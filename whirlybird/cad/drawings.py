"""PDF drawing set (reportlab). Line work comes from hidden-line projection of the real
build123d solids; dimensions are taken from the same derived parameters the CAD uses."""
from __future__ import annotations

import datetime
import math

import numpy as np
from build123d import Compound, Keep, Plane, split
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import flatpattern as FP
from params import bow_offset, blade_frame

PW, PH = landscape(letter)          # points
GRAY = Color(0.45, 0.45, 0.45)
BLUE = Color(0.1, 0.25, 0.7)
RED = Color(0.75, 0.1, 0.1)
ORANGE = Color(0.85, 0.42, 0.1)
REV = "DW-V1.1"
TODAY = datetime.date.today().isoformat()


# ------------------------------------------------------------------ basics --
class Sheet:
    def __init__(self, c: canvas.Canvas, title: str, scale: str = "NTS", portrait=False):
        self.c, self.title, self.scale = c, title, scale
        self.w, self.h = (letter if portrait else (PW, PH))
        self.portrait = portrait

    def frame(self, n, total):
        c = self.c
        c.setLineWidth(0.8)
        c.rect(6 * mm, 6 * mm, self.w - 12 * mm, self.h - 12 * mm)
        tbw, tbh = 118 * mm, 24 * mm
        x0, y0 = self.w - 6 * mm - tbw, 6 * mm
        c.rect(x0, y0, tbw, tbh)
        c.line(x0, y0 + 12 * mm, x0 + tbw, y0 + 12 * mm)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x0 + 2 * mm, y0 + 17 * mm, "DOGHOUSE WHIRLYBIRD - 8 BLADE ROTOR")
        c.setFont("Helvetica", 8)
        c.drawString(x0 + 2 * mm, y0 + 13.5 * mm, self.title[:70])
        c.setFont("Helvetica", 7)
        c.drawString(x0 + 2 * mm, y0 + 8 * mm, f"REV {REV}   UNITS mm   SCALE {self.scale}   {TODAY}")
        c.drawString(x0 + 2 * mm, y0 + 3.5 * mm, f"SHEET {n}/{total}   Source: build123d parametric model + MASTER_PARAMETERS.json")

    def text(self, x, y, s, size=8, bold=False, color=black):
        self.c.setFillColor(color)
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.drawString(x * mm, y * mm, s)
        self.c.setFillColor(black)

    def lines(self, x, y, rows, size=7.5, lead=1.35, bold_first=False):
        for k, r in enumerate(rows):
            self.text(x, y - k * size * lead * 0.3528, r, size, bold=(bold_first and k == 0))
        return y - len(rows) * size * lead * 0.3528

    def image(self, path, x, y, w, h):
        img = ImageReader(str(path))
        iw, ih = img.getSize()
        s = min(w / iw, h / ih)
        dw, dh = iw * s, ih * s
        self.c.drawImage(img, (x + (w - dw) / 2) * mm, (y + (h - dh) / 2) * mm, dw * mm, dh * mm)
        self.c.setLineWidth(0.3)
        self.c.setStrokeColor(GRAY)
        self.c.rect(x * mm, y * mm, w * mm, h * mm)
        self.c.setStrokeColor(black)

    def table(self, x, y, rows, widths, size=7, row_h=4.2, header=True):
        c = self.c
        for i, r in enumerate(rows):
            yy = y - (i + 1) * row_h
            xx = x
            if header and i == 0:
                c.setFillColor(Color(0.88, 0.88, 0.9))
                c.rect(x * mm, yy * mm, sum(widths) * mm, row_h * mm, fill=1, stroke=0)
                c.setFillColor(black)
            for w, cell in zip(widths, r):
                c.setFont("Helvetica-Bold" if (header and i == 0) else "Helvetica", size)
                c.drawString((xx + 1) * mm, (yy + 1.2) * mm, str(cell)[: int(w * 2.3 / size * 6)])
                xx += w
            c.setLineWidth(0.2)
            c.line(x * mm, yy * mm, (x + sum(widths)) * mm, yy * mm)
        return y - len(rows) * row_h


class View:
    """Maps model 2-D coords (mm) to page coords (mm) at a given scale."""

    def __init__(self, sheet, x0, y0, scale, flipx=False):
        self.s, self.x0, self.y0, self.k, self.fx = sheet, x0, y0, scale, flipx

    def P(self, x, y):
        return (self.x0 + (-x if self.fx else x) * self.k, self.y0 + y * self.k)

    def edges(self, edges, width=0.5, color=black, dash=None, n=24):
        c = self.s.c
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.setDash(list(dash), 0) if dash else c.setDash()
        for e in edges:
            try:
                if e.geom_type.name == "LINE":
                    pts = [e.start_point(), e.end_point()]
                else:
                    pts = e.positions(np.linspace(0, 1, max(n, int(e.length / 1.5))))
            except Exception:
                continue
            p = c.beginPath()
            x, y = self.P(pts[0].X, pts[0].Y)
            p.moveTo(x * mm, y * mm)
            for q in pts[1:]:
                x, y = self.P(q.X, q.Y)
                p.lineTo(x * mm, y * mm)
            c.drawPath(p, stroke=1, fill=0)
        c.setDash()
        c.setStrokeColor(black)

    def poly(self, pts, width=0.5, color=black, dash=None, close=False, fill=None):
        c = self.s.c
        c.setStrokeColor(color)
        c.setLineWidth(width)
        c.setDash(list(dash), 0) if dash else c.setDash()
        p = c.beginPath()
        x, y = self.P(*pts[0])
        p.moveTo(x * mm, y * mm)
        for q in pts[1:]:
            x, y = self.P(*q)
            p.lineTo(x * mm, y * mm)
        if close:
            p.close()
        if fill is not None:
            c.setFillColor(fill)
        c.drawPath(p, stroke=1, fill=1 if fill is not None else 0)
        c.setFillColor(black)
        c.setDash()
        c.setStrokeColor(black)

    def dim(self, a, b, off, label, vertical=False, size=7, color=BLUE):
        """Linear dimension between model points a,b with offset `off` (model mm) perpendicular."""
        c = self.s.c
        (ax, ay), (bx, by) = self.P(*a), self.P(*b)
        o = off * self.k
        if vertical:
            xa = max(ax, bx) + o if o > 0 else min(ax, bx) + o
            p1, p2 = (xa, ay), (xa, by)
            ext = [((ax, ay), p1), ((bx, by), p2)]
        else:
            ya = max(ay, by) + o if o > 0 else min(ay, by) + o
            p1, p2 = (ax, ya), (bx, ya)
            ext = [((ax, ay), p1), ((bx, by), p2)]
        c.setStrokeColor(color)
        c.setFillColor(color)
        c.setLineWidth(0.25)
        for (u, v) in ext:
            c.line(u[0] * mm, u[1] * mm, v[0] * mm, v[1] * mm)
        c.line(p1[0] * mm, p1[1] * mm, p2[0] * mm, p2[1] * mm)
        for (p, q) in ((p1, p2), (p2, p1)):
            ang = math.atan2(q[1] - p[1], q[0] - p[0])
            L = 2.2
            for s in (0.35, -0.35):
                c.line(p[0] * mm, p[1] * mm, (p[0] + L * math.cos(ang + s)) * mm, (p[1] + L * math.sin(ang + s)) * mm)
        c.setFont("Helvetica", size)
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        if vertical:
            c.saveState()
            c.translate((mx - 1.2) * mm, my * mm)
            c.rotate(90)
            c.drawCentredString(0, 0, label)
            c.restoreState()
        else:
            c.drawCentredString(mx * mm, (my + 1.0) * mm, label)
        c.setStrokeColor(black)
        c.setFillColor(black)

    def note(self, at, text_at, label, size=7, color=BLUE):
        c = self.s.c
        (x1, y1), (x2, y2) = self.P(*at), self.P(*text_at)
        c.setStrokeColor(color)
        c.setFillColor(color)
        c.setLineWidth(0.25)
        c.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)
        c.circle(x1 * mm, y1 * mm, 0.5 * mm, fill=1)
        c.setFont("Helvetica", size)
        c.drawString((x2 + 0.8) * mm, (y2 - 0.8) * mm, label)
        c.setStrokeColor(black)
        c.setFillColor(black)


def hlr(shape, origin, up, look):
    vis, hid = shape.project_to_viewport(origin, up, look)
    return vis, hid


def half(shapes, plane=Plane.XZ, keep=Keep.BOTTOM):
    out = []
    for s in shapes:
        try:
            r = split(s, plane, keep=keep)
        except Exception:
            continue
        if r is not None and r.volume > 1e-6:
            out.append(r)
    return Compound(children=out)


# ------------------------------------------------------------------- sheets --
def sheet_cover(S, P, D, report, renders):
    S.text(14, 196, "DOGHOUSE WHIRLYBIRD - CAD / FABRICATION PACKAGE", 15, True)
    S.text(14, 189, f"Rev {REV} - generated {TODAY} from the parametric build123d model (whirlybird/cad) and MASTER_PARAMETERS.json", 8)
    S.image(renders / "assembly_iso.png", 14, 102, 120, 82)
    y = S.lines(140, 182, [
        "COORDINATE SYSTEM / DATUMS",
        "Z0 = finished roof surface at the rotor axis.  +Z = rotor axis (roof to sky).",
        "X/Y = plan. Blade 1 tab centre on +X axis; blades numbered CCW seen from above.",
        "Datum A = shaft axis.  Datum B = lower-hub top face (blade shoulder seat).",
        "All STEP files share this origin; STL files are re-posed for printing.",
    ], 8, bold_first=True)
    rows = [["Key result (from CAD)", "Value"],
            ["Installed height, roof to rotor top", f"{D['installed_height']:.1f} mm ({D['installed_height'] / 25.4:.2f} in)  limit 190.5"],
            ["Rotor OD incl. bowed blades", f"{D['rotor_od_actual']:.1f} mm ({D['rotor_od_actual'] / 25.4:.2f} in)  target 266.7"],
            ["Rotor OD at cap faces", f"{D['rotor_od_at_cap_faces']:.1f} mm"],
            ["Hub OD upper / lower", f"{P['upper_hub']['od']:.0f} / {P['lower_hub']['od']:.0f} mm"],
            ["Cap separation (blade shoulders)", f"{D['cap_separation']:.2f} mm (bow {P['blade']['bow_sagitta']:.0f} mm)"],
            ["Blade chord angle from radial", f"{P['blade']['plan_chord_angle_from_radial']:.0f} deg, all same hand"],
            ["Min blade-to-blade clearance", f"{D['neighbour_min_clearance_sampled'] - P['blade']['thickness']:.1f} mm"],
            ["Rotor-to-stationary axial gap", f"{P['stationary']['rotor_to_stationary_axial_gap']:.1f} mm (labyrinth 2.0 radial)"],
            ["Bearing spacing / shaft length", f"{P['bearings']['center_separation']:.0f} mm / {D['shaft_length']:.1f} mm"],
            ["Throat (roof opening)", f"{P['stationary']['throat_id']:.0f} mm  (5 in hole saw)"],
            ["Height margin to 190.5 limit", f"{D['height_margin_to_limit']:.1f} mm"]]
    S.table(140, 152, rows, [62, 66], size=7)
    g = report["gates"]
    S.text(14, 97, f"DESIGN GATES ({sum(x['pass'] for x in g)}/{len(g)} PASS) - see sheet 12 and whirlybird/reports/design_checks.json", 8, True)
    rows = [["#", "Gate (automated on the CAD)", "Result"]] + [[str(i + 1), x["gate"][:92], "PASS" if x["pass"] else "FAIL"] for i, x in enumerate(g)]
    S.table(14, 94, rows, [6, 150, 14], size=6.1, row_h=3.4)
    S.lines(190, 82, ["SHEET INDEX", "1 Cover / datums / results", "2 Axial section, height stack", "3 Rotor vs stationary",
                      "4 Exploded assembly + order", "5 True CAD views", "6 Upper hub", "7 Lower hub", "8 Bearing support",
                      "9 Roof flash adapter", "10 Blade 1:1 + forming", "11 Coupons + tooling", "12 Checks + calcs"], 7, bold_first=True)


def sheet_section(S, P, D, items, renders):
    shapes = [it.shape for it in items]
    cut = half(shapes)
    vis, hid = hlr(cut, (0, -3000, 50), (0, 0, 1), (0, 0, 50))
    V = View(S, 95, 92, 0.5)   # 1:2, model (x, z-50)
    V.edges(vis, 0.35)
    # translate: hlr y = z - 50
    def Z(z):
        return z - 50
    V.poly([(-140, Z(0)), (140, Z(0))], 0.4, Color(0.5, 0.3, 0.1), (4, 2))
    S.text(*(np.array(V.P(70, Z(0))) + (0, 1.2)), "FINISHED ROOF SURFACE  Z0 (DATUM)", 6, color=Color(0.5, 0.3, 0.1))
    xL = -150
    V.dim((0, Z(D["z_lower_face"])), (0, Z(D["z_upper_face"])), xL + 18, f"{D['cap_separation']:.1f} CAP SEPARATION", True)
    V.dim((0, Z(0)), (0, Z(D["z_rotor_top"])), xL + 6, f"{D['installed_height']:.1f} INSTALLED HEIGHT (MAX 190.5)", True)
    V.dim((0, Z(D["z_upper_bearing_center"])), (0, Z(D["z_lower_bearing_center"])), 40, "50 BRG", True)
    V.dim((0, Z(D["z_shaft_bottom"])), (0, Z(D["z_shaft_top"])), 150, f"SHAFT {D['shaft_length']:.1f}", True)
    V.dim((0, Z(D["z_rotor_top"])), (P["upper_hub"]["od"] / 2, Z(D["z_rotor_top"])), 8, f"R{P['upper_hub']['od'] / 2:.0f} HUB")
    rmax = D["rotor_od_actual"] / 2
    V.dim((0, Z(D["z_lower_face"] + D["cap_separation"] / 2)), (rmax, Z(D["z_lower_face"] + D["cap_separation"] / 2)), 0,
          f"R{rmax:.1f} ROTOR")
    V.dim((-P["stationary"]["throat_id"] / 2, Z(-6)), (P["stationary"]["throat_id"] / 2, Z(-6)), -30, "THROAT 127")
    V.dim((-P["stationary"]["flange_od"] / 2, Z(-6)), (P["stationary"]["flange_od"] / 2, Z(-6)), -52, "FLANGE 230")
    V.note((0, Z(D["z_rotor_top"])), (-120, Z(200)), "CLOSED TOP - no openings")
    V.note((-P["pocket"]["tab_center_radius"], Z(D["z_upper_face"] + 4)), (-120, Z(192)), "BLIND POCKET - opens DOWN only")
    V.note((-P["pocket"]["tab_center_radius"], Z(D["z_lower_face"] - 4)), (-160, Z(-80)), "BLIND POCKET - opens UP only")
    V.note((-30, Z(D["z_lower_hub_bottom"])), (-160, Z(-88)), "LOWER HUB closed under every pocket")
    V.note((-13, Z(D["z_upper_bearing_top"] - 2)), (-160, Z(-96)), "ROTATING cup over STATIONARY tower, 2 mm labyrinth")
    rows = [["Height stack (Z, mm)", "from", "to", "size"],
            ["Roof to collar/support top", "0", f"{D['z_collar_top']:.1f}", f"{D['z_collar_top']:.1f}"],
            ["Rotor-to-stationary gap", f"{D['z_collar_top']:.1f}", f"{D['z_lower_hub_bottom']:.1f}", "6.0"],
            ["Lower hub", f"{D['z_lower_hub_bottom']:.1f}", f"{D['z_lower_face']:.1f}", "12.0"],
            ["Blade shoulders (cap sep.)", f"{D['z_lower_face']:.1f}", f"{D['z_upper_face']:.2f}", f"{D['cap_separation']:.2f}"],
            ["Upper hub", f"{D['z_upper_face']:.2f}", f"{D['z_rotor_top']:.2f}", "12.0"],
            ["Bearing centres", f"{D['z_lower_bearing_center']:.2f}", f"{D['z_upper_bearing_center']:.2f}", "50.0"],
            ["Shaft", f"{D['z_shaft_bottom']:.2f}", f"{D['z_shaft_top']:.2f}", f"{D['shaft_length']:.2f}"]]
    S.table(198, 76, rows, [36, 11, 12, 13], size=5.6, row_h=3.3)
    S.text(14, 200, "SHEET 2 - AXIAL HALF-SECTION (plane XZ, true CAD hidden-line projection, 1:2) + HEIGHT STACK", 10, True)
    S.image(renders / "section_bearing_detail.png", 198, 132, 72, 48)
    S.text(198, 182, "Bearing / labyrinth detail (render)", 7, True)
    S.image(renders / "pocket_section_lower.png", 198, 82, 72, 38)
    S.text(198, 122, "Lower pocket detail: tab, R2 roots, blind floor, weep", 7, True)


def sheet_rotor_stator(S, P, D, items, renders):
    S.text(14, 200, "SHEET 3 - ROTOR vs STATIONARY: what turns, what is fixed to the roof, and how each attaches", 10, True)
    S.image(renders / "rotor_vs_stationary_section.png", 12, 92, 128, 100)
    S.image(renders / "rotor_lifted_off_stationary.png", 145, 92, 128, 100)
    rows = [["ROTATING part (orange)", "Attaches to", "By"],
            ["Upper hub (closed top)", "shaft (blind bore)", "1x M4 set screw in nut slot -> shaft dimple"],
            ["Lower hub (closed bottom)", "shaft", "1x M4 set screw in nut slot -> shaft dimple"],
            ["8 blades", "both hubs", "tabs trapped in blind pockets (no fasteners)"],
            ["Shaft 1/4 in", "bearing INNER races", "slip fit; lower hub bears on top inner race via washer"],
            ["Top thrust washer", "upper bearing inner race", "loose on shaft, under lower-hub cup"],
            ["Shaft collar + bottom washer", "lower bearing inner race", "collar set screw (uplift stop, 0.2 endplay)"]]
    S.table(12, 88, rows, [40, 38, 66], size=6.2)
    rows = [["STATIONARY part (blue)", "Attaches to", "By"],
            ["Roof flash adapter", "roof deck", "8x #8 SS screws + sealant bead in groove"],
            ["Bearing support (ring/spokes/tower)", "adapter collar counterbore", "rests on step; 3x M3 radial screws"],
            ["2x R4-2RS bearing OUTER races", "bearing support tower", "pressed into seats (fit per coupon)"],
            ["Rain tray (optional)", "tower bottom (below roof)", "slip-on standpipe + 1x M3 clamp screw"]]
    S.table(158, 88, rows, [40, 32, 43], size=5.8)
    S.lines(12, 52, ["NO stationary part is fastened to either rotating hub. The only paths between rotor and stator are the two",
                     "ball bearings. Minimum running clearances (from CAD): 6.0 mm lower hub to collar/support ring, 2.0 mm radial",
                     f"labyrinth (cup vs tower), {D['neighbour_min_clearance_sampled'] - P['blade']['thickness']:.0f} mm blade to blade, >13 mm blade to any stationary part.",
                     "Service: remove 3 M3 screws -> the whole rotor + bearing cartridge lifts out of the roof adapter."], 7.5)


def sheet_exploded(S, P, D, renders):
    S.text(14, 200, "SHEET 4 - EXPLODED ASSEMBLY (true CAD) AND ASSEMBLY ORDER", 10, True)
    S.image(renders / "assembly_exploded.png", 12, 22, 110, 172)
    steps = [
        "ASSEMBLY ORDER (proved collision-free in CAD, gate 10):",
        "1  Press both R4-2RS bearings into the support tower (top seat from above,",
        "   bottom seat from below) - fit chosen from the fit coupon.",
        "2  Bottom washer + 1/4 in shaft collar loosely on the shaft; slide shaft UP",
        "   through both bearings from below.",
        "3  Top thrust washer onto the shaft, on the upper inner race.",
        "4  Lower hub down the shaft until its cup ceiling sits on the washer.",
        "   Mark through the set-screw hole; spot-drill dimple (guide); M4 set",
        "   screw + nut, threadlocker. Set collar for 0.2 mm endplay.",
        "5  Drop each blade's lower tab straight DOWN into a lower-hub pocket",
        "   (same orientation for all 8: bow outward, tab at inner edge).",
        "6  Lower the upper hub straight DOWN over all 8 upper tabs (lead-in",
        "   chamfers align them). Press lightly until every shoulder seats.",
        "7  Mark, spot-drill the 2nd dimple, tighten upper set screw (thread-",
        "   locker). Blades are now trapped: no per-blade hardware.",
        "8  Spin by hand: no rub, no rattle. Static-balance (tape on hub rim).",
        "9  Fasten roof adapter (sealant + 8 screws); drop the rotor cartridge",
        "   into the collar; 3x M3 radial screws. Optional tray underneath.",
    ]
    S.lines(128, 190, steps, 7.6, bold_first=True)
    S.lines(128, 92, ["Exploded offsets are along +Z only, matching the real",
                      "assembly direction: blades enter the lower hub from ABOVE;",
                      "the upper hub comes DOWN over the upper tabs. No part has",
                      "to be threaded over an already-bent blade."], 7.5)
    S.image(renders / "assembly_exploded_side.png", 200, 22, 72, 72)


def sheet_views(S, renders):
    S.text(14, 200, "SHEET 5 - TRUE CAD-RENDERED VIEWS (tessellated build123d solids)", 10, True)
    for (img, label, x, y) in (("view_top.png", "TOP", 12, 108), ("view_side.png", "SIDE", 142, 108),
                               ("view_underside.png", "UNDERSIDE", 12, 22), ("assembly_iso_from_below.png", "ISO FROM BELOW", 142, 22)):
        S.image(renders / img, x, y, 126, 84)
        S.text(x + 2, y + 79, label, 8, True)


def _hub_sheet(S, P, D, hub, name, renders, upper):
    S.text(14, 200, f"SHEET {6 if upper else 7} - {name.upper().replace('_', ' ')}  (print {'TOP FACE DOWN' if upper else 'BOTTOM DOWN'})", 10, True)
    zf = D["z_upper_face"] if upper else D["z_lower_face"]
    # plan view from the pocket side
    if upper:
        vis, _ = hlr(hub, (0, 0, -3000), (0, 1, 0), (0, 0, 0))
        V = View(S, 62, 120, 0.5, flipx=False)
    else:
        vis, _ = hlr(hub, (0, 0, 3000), (0, 1, 0), (0, 0, 0))
        V = View(S, 62, 120, 0.5)
    V.edges(vis, 0.3)
    rho = P["pocket"]["tab_center_radius"]
    V.poly([(rho * math.cos(a), rho * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 120)], 0.25, RED, (6, 2, 1, 2))
    R = P["upper_hub"]["od"] / 2 if upper else P["lower_hub"]["od"] / 2
    V.dim((-R, 0), (R, 0), -R - 8, f"OD {2 * R:.0f}")
    V.note((rho, 0), (-100, 113), f"8x BLIND POCKET {D['pocket_length']:.1f} x {P['pocket']['width']:.2f} x {P['pocket']['depth']:.1f} DEEP")
    V.note((rho * math.cos(math.pi / 4), rho * math.sin(math.pi / 4)), (-100, 105), f"POCKET CENTRES ON R{rho:.1f}, 8x45 deg")
    th = P["blade"]["plan_chord_angle_from_radial"]
    V.note((rho * math.cos(math.pi), rho * math.sin(math.pi)), (-100, -118), f"POCKET LONG AXIS {th:.0f} deg FROM RADIAL (all same hand)")
    S.text(14, 186, "PLAN FROM " + ("BELOW (pocket face)" if upper else "ABOVE (pocket face)") + "  1:2", 7.5, True)
    # half section
    cut = half([hub])
    vis2, _ = hlr(cut, (0, -3000, zf), (0, 0, 1), (0, 0, zf))
    V2 = View(S, 165, 160, 0.5)
    V2.edges(vis2, 0.3)
    T_ = P["upper_hub"]["thickness"] if upper else P["lower_hub"]["thickness"]
    if upper:
        V2.dim((R, 0), (R, T_), 6, f"{T_:.0f}", True)
        V2.dim((0, -P["upper_hub"]["boss_length_below_face"]), (0, 0), -16, f"{P['upper_hub']['boss_length_below_face']:.0f}", True)
    else:
        V2.dim((R, -T_), (R, 0), 6, f"{T_:.0f}", True)
        V2.dim((70, 0), (70, P["lower_hub"]["chimney_height_above_face"]), 8, f"{P['lower_hub']['chimney_height_above_face']:.0f}", True)
    S.text(140, 186, "HALF SECTION XZ  1:2", 7.5, True)
    S.image(renders / (("upper_hub_underside_blind_pockets.png") if upper else ("lower_hub_top_blind_pockets.png")), 140, 96, 64, 50)
    S.image(renders / (("upper_hub_top_closed.png") if upper else ("lower_hub_bottom_closed.png")), 206, 96, 64, 50)
    S.text(141, 92, "pockets visibly BLIND" if upper else "pockets open UP only", 6.5)
    S.text(207, 92, "closed exterior TOP" if upper else "closed exterior BOTTOM", 6.5)
    K, F = P["pocket"], P["hub_fixing"]
    rows = [["Feature", "Value"],
            ["Pocket width (coupon-selected)", f"{K['width']:.2f} (try 1.85/1.95/2.05/2.15)"],
            ["Pocket length / depth", f"{D['pocket_length']:.1f} / {K['depth']:.1f}  (tab 14 x 7)"],
            ["Mouth lead-in", f"ends {K['mouth_end_chamfer']:.1f} x45, sides {K['mouth_side_lead_in']:.1f}"],
            ["Intact wall over/under pocket", f"{D['upper_hub_roof_over_pocket']:.1f} mm"],
            ["Wall pocket->OD (mouth / deep)", f"{D['upper_hub_shell_outside_pocket']:.2f} / {D['upper_hub_shell_outside_pocket_below_mouth']:.2f}"],
            ["Shaft bore", f"{P['shaft']['hub_bore_diameter']:.2f} {'BLIND' if upper else 'through boss'}"],
            ["Set screw", f"M4 x6 cup, nut slot {F['nut_slot_width']}x{F['nut_slot_thickness']}, at {26.0:.0f} deg az"],
            ["Set screw height", f"Z {D['z_upper_set_screw'] if upper else D['z_lower_set_screw']:.2f}"]]
    if upper:
        rows += [["Drip lip", f"{P['upper_hub']['drip_lip_width']} x {P['upper_hub']['drip_lip_height']} notched at blades"],
                 ["Centre web / ribs", f"{P['upper_hub']['center_web_thickness']} mm web, {P['upper_hub']['rib_count']} ribs"]]
    else:
        rows += [["Weep channels", f"8x {P['lower_hub']['weep_channel_size']} diamond, pocket floor -> OD, 2 deg fall"],
                 ["Chimney ID / spokes", f"{P['lower_hub']['chimney_id']:.0f} / {P['lower_hub']['spoke_count']} x {P['lower_hub']['spoke_width']:.0f} mm"],
                 ["Labyrinth cup", f"ID {P['stationary']['tower_od'] + 2 * P['stationary']['labyrinth_radial_gap']:.0f}, ceiling Z {D['z_cup_ceiling']:.1f}"]]
    S.table(140, 88, rows, [55, 75], size=6.5, row_h=3.9)


def sheet_support(S, P, D, items, renders):
    sup = next(it.shape for it in items if it.name == "bearing_support_stationary")
    S.text(14, 200, "SHEET 8 - BEARING SUPPORT (STATIONARY)  print TOWER-TOP DOWN, supports under ring/spokes", 10, True)
    cut = half([sup])
    vis, _ = hlr(cut, (0, -3000, 0), (0, 0, 1), (0, 0, 0))
    V = View(S, 80, 120, 1.0)
    V.edges(vis, 0.35)
    BR = P["bearings"]
    V.dim((0, D["z_tower_top"]), (0, D["z_tower_bottom"]), -30, f"TOWER {D['tower_length']:.2f}", True)
    V.dim((0, D["z_upper_bearing_center"]), (0, D["z_lower_bearing_center"]), 22, f"{BR['center_separation']:.0f} BRG CTRS", True)
    V.dim((-BR["seat_bore_diameter"] / 2, D["z_tower_top"]), (BR["seat_bore_diameter"] / 2, D["z_tower_top"]), 8, f"SEAT {BR['seat_bore_diameter']:.2f} x {BR['width']:.2f} DEEP")
    V.dim((-P["stationary"]["tower_od"] / 2, D["z_tower_bottom"]), (P["stationary"]["tower_od"] / 2, D["z_tower_bottom"]), -8, f"OD {P['stationary']['tower_od']:.0f}")
    V.dim((-66.4, D["z_collar_top"]), (66.4, D["z_collar_top"]), 14, "RING OD 132.8 / ID 127")
    V.note((0, 0), (40, -20), "MID BORE 11 (shaft clearance)")
    V.note((63, D["z_collar_top"] - 5), (40, 40), "3x M3 PILOT 2.6 RADIAL (self-tap)")
    S.text(14, 186, "HALF SECTION XZ  1:1", 7.5, True)
    S.image(renders / "bearing_support_stationary.png", 180, 100, 90, 80)
    S.lines(180, 92, ["Notes:", "- Bearing OUTER races only are held here.", "- Seat bores from fit coupon; do not",
                      "  print hard interference before testing.", "- Gussets under each spoke stiffen the",
                      "  43 mm tower below the ring.", "- Ring top flush with collar top: 6 mm",
                      "  below the rotating lower hub."], 7.5)


def sheet_adapter(S, P, D, items, report, renders):
    ad = next(it.shape for it in items if it.name == "roof_flash_adapter")
    S.text(14, 200, f"SHEET 9 - ROOF FLASH ADAPTER (STATIONARY)  pitch modelled = {P['roof_pitch_deg']:.1f} deg", 10, True)
    cut = half([ad])
    vis, _ = hlr(cut, (0, -3000, 0), (0, 0, 1), (0, 0, 0))
    V = View(S, 80, 160, 0.6)
    V.edges(vis, 0.35)
    S_ = P["stationary"]
    V.dim((-S_["flange_od"] / 2, 0), (S_["flange_od"] / 2, 0), -14, f"FLANGE OD {S_['flange_od']:.0f}")
    V.dim((-S_["throat_id"] / 2, D["z_collar_top"]), (S_["throat_id"] / 2, D["z_collar_top"]), 10, f"THROAT {S_['throat_id']:.0f}")
    V.dim((S_["flange_od"] / 2, 0), (S_["flange_od"] / 2, D["z_collar_top"]), 8, f"{D['z_collar_top']:.0f}", True)
    S.text(14, 186, "HALF SECTION XZ  1:1.67", 7.5, True)
    S.image(renders / "roof_flash_adapter.png", 178, 120, 92, 70)
    rows = [["Roof pitch file", "deg", "Collar top Z", "Installed height", "<=190.5"]]
    for r in report["roof_pitch_table"]:
        rows.append([f"roof_flash_adapter_pitch_{r['pitch']}.stl", r["deg"], r["collar_top_at_axis"], r["installed_height"], "YES" if r["within_190p5"] else "NO"])
    S.table(14, 118, rows, [70, 14, 24, 30, 16], size=6.8)
    S.lines(14, 88, ["ROOF CUT-OUT: 127 mm (5 in) hole saw, centred. Seal the plywood cut edge with exterior paint.",
                     f"FASTEN: {S_['flange_screw_count']}x #8 x 3/4 in stainless pan-head wood screws with EPDM washers on a {S_['flange_screw_circle']:.0f} mm circle.",
                     f"SEAL: continuous bead of butyl / polyurethane in the {S_['gasket_groove_width']:.0f} x {S_['gasket_groove_depth']} mm groove (R{S_['gasket_groove_radius']:.0f}),",
                     "       plus a fillet bead round the flange edge on the UPHILL half. On shingles, slip the uphill half under",
                     "       the course above (no sealant needed there) - classic step-flash logic.",
                     "PITCH: real pitch unknown. Pitched files tilt the flange; the collar stays vertical. Above ~5/12",
                     "       the 190.5 mm limit is exceeded because the rotor must lift to clear the uphill roof.",
                     "SUPPORT: bearing-support ring drops into the counterbore and rests on the step; 3x M3 screws radial."], 7.4)


def sheet_blade(S, P, D, report, renders):
    S.scale = "1:1 (blade)"
    S.text(14, 200, "SHEET 10 - BLADE: FLAT PATTERN 1:1, FORMED PROFILE 1:1, FORMING", 10, True)
    segs = FP.outline(P, D)
    an = FP.annotations(P, D)
    V = View(S, 30, 30, 1.0)
    V.poly(FP.polyline_points(segs, 3), 0.5, close=True)
    V.poly([(an["tab_centerline_x"], -4), (an["tab_centerline_x"], an["L"] + 4)], 0.25, RED, (6, 2, 1, 2))
    for ys in an["shoulder_y"]:
        V.poly([(-3, ys), (an["W"] + 3, ys)], 0.25, Color(0.1, 0.5, 0.1), (2, 1))
    V.poly([(-3, an["bow_peak_y"]), (an["W"] + 3, an["bow_peak_y"])], 0.25, RED, (6, 2, 1, 2))
    B = P["blade"]
    V.dim((0, an["L"] - B["tab_length"]), (an["W"], an["L"] - B["tab_length"]), 14, f"{B['body_chord']:.2f}")
    V.dim((0, 0), (0, an["L"]), -10, f"{B['blank_length']:.1f} BLANK", True)
    V.dim((B["tab_inner_margin"], 0), (B["tab_inner_margin"] + B["tab_width"], 0), -5, f"TAB {B['tab_width']:.0f}")
    V.dim((0, an["L"]), (B["tab_inner_margin"], an["L"]), 5, f"{B['tab_inner_margin']:.0f}")
    V.dim((an["W"], 0), (an["W"], B["tab_length"]), 6, f"{B['tab_length']:.0f}", True)
    V.dim((an["W"], B["tab_length"]), (an["W"], an["L"] - B["tab_length"]), 6, f"{D['blade_developed_body_length']:.1f} BODY (developed)", True)
    V.note((B["tab_inner_margin"] + B["tab_width"] + 1.2, B["tab_length"] + 0.8), (40, 20), "R2 ROOT x4")
    V.note((B["tab_inner_margin"] + 0.5, 0.5), (-14, 10), "1x45 TIP")
    V.note((an["W"] - 0.6, an["L"] - B["tab_length"] - 0.6), (66, 120), "R2 CORNERS (deburr)")
    S.text(30 + an["W"] + 22, 27, "INNER EDGE = toward shaft (x=0)", 6.5)
    # formed profile 1:1
    H, s = D["cap_separation"], B["bow_sagitta"]
    V2 = View(S, 125, 30 + B["tab_length"], 1.0)
    z = np.linspace(0, H, 121)
    w = bow_offset(z, s, H)
    V2.poly([(0, -B["tab_length"])] + list(zip(w, z)) + [(0, H + B["tab_length"])], 0.6, BLUE)
    V2.poly([(0, -B["tab_length"]), (0, H + B["tab_length"])], 0.25, GRAY, (3, 2))
    V2.dim((0, 0), (0, H), -8, f"{H:.2f} CAP SEPARATION", True)
    V2.dim((0, H / 2), (s, H / 2), 3, f"{s:.0f}")
    V2.note((s * 0.5, H * 0.18), (30, 30), "d(z) = s sin^2(pi z / H)")
    V2.note((0, 0), (6, -12), "SHOULDER")
    S.text(118, 172, "FORMED SIDE PROFILE 1:1 (lay blade on it)", 7, True)
    fd = report["forming_die"]
    S.lines(175, 186, ["CUT (gate C: ONE blade first)",
                       "- Rip stock 3.75 in -> 57.15 mm; crosscut 139.7 mm;",
                       "  file to the line; kerf on the WASTE side.",
                       "- Notch tabs: saw/snips to 2 mm short of the shoulder,",
                       "  file R2 roots (no sharp inside corners).",
                       "- Break all edges; R2 outer corners; 1x45 tab tips.",
                       "- No holes in the blade.",
                       "",
                       "FORM (printed press die, bench vise)",
                       f"- Die sagitta {fd['die_sagitta']:.1f} mm = {s:.0f} x springback {fd['springback_factor']:.2f}.",
                       "- Lower die keys only accept the blank tab-side correct.",
                       "- Squeeze slowly until faces meet; release; measure.",
                       f"- Target bow {s:.0f} +/-1.5 mm; shoulders {H:.1f} +/-0.5 apart.",
                       "- Too flat -> raise springback factor, reprint die.",
                       "- Tabs must stay flat, in line, and parallel.",
                       "",
                       "ORIENTATION IN ROTOR",
                       "- Tab toward the shaft-side edge; bow bulges OUTWARD.",
                       "- All 8 identical; all same hand."], 7.2, bold_first=True)
    S.image(renders / "forming_die_open.png", 175, 36, 95, 54)


def sheet_coupons(S, P, renders):
    S.text(14, 200, "SHEET 11 - PRINT THESE FIRST: FIT COUPONS AND TOOLING", 10, True)
    cells = [("print_single_blade_socket_test_top.png", "single_blade_socket_test_top (closed top, opens down)"),
             ("print_single_blade_socket_test_bottom.png", "single_blade_socket_test_bottom (opens up, weep)"),
             ("print_slot_clearance_coupon_1p85_1p95_2p05_2p15.png", "slot_clearance_coupon 1.85 / 1.95 / 2.05 / 2.15"),
             ("print_bearing_and_shaft_fit_coupon.png", "bearing seats 15.80-16.10, shaft bores 6.45-6.65"),
             ("print_shaft_dimple_drill_guide.png", "shaft_dimple_drill_guide (3.5 mm spot)"),
             ("print_inlet_vent_louver.png", "inlet_vent_louver x2 (screened, 45 deg)")]
    for k, (img, lab) in enumerate(cells):
        x = 12 + (k % 3) * 88
        y = 120 if k < 3 else 48
        S.image(renders / img, x, y, 84, 62)
        S.text(x + 1, y - 4, lab, 6.8)
    S.lines(12, 38, ["PASS CRITERIA (gate B): 1.6 mm aluminium tab slides in by hand, does not rock more than ~0.3 mm at the tip,",
                     "no whitening/cracking or layer splitting when wiggled, cannot be pushed through any outer face. Choose the",
                     "narrowest slot that passes, enter it in MASTER_PARAMETERS.json (pocket.width) and rebuild. Bearings: firm",
                     "thumb-press, no rattle. Shaft bore: slides with light force, no wobble."], 7.5)


def sheet_checks(S, P, D, report):
    S.text(14, 200, "SHEET 12 - AUTOMATED CAD CHECKS, CALCULATIONS AND OPEN ITEMS", 10, True)
    cc = D["centrifugal_check"]
    rows = [["Calculation", "Value", "Comment"],
            ["Blade mass (1.6 Al)", f"{D['blade_mass_g']:.1f} g", f"set of {P['blade_count']}: {D['blade_mass_g'] * P['blade_count']:.0f} g"],
            ["Centrifugal load @1000 rpm", f"{cc['force_per_blade_N']:.1f} N/blade", f"CG radius {cc['blade_cg_radius_mm']:.0f} mm"],
            ["Per tab", f"{cc['force_per_tab_N']:.1f} N", f"bearing stress {cc['tab_bearing_stress_MPa']:.1f} MPa on 1.6x7 tab"],
            ["Proof pull target", "50 N per tab", f"= {cc['proof_vs_1000rpm_ratio']:.1f}x the 1000 rpm load; keep"],
            ["Pocket end-wall shear-out", "> 1 kN est.", "4 mm wall x 8.5 deep x 2 shear planes x ~15 MPa"],
            ["Hub hoop stress @1000 rpm", "< 0.1 MPa", "negligible"],
            ["Thermal (Al vs SS shaft, 60 K)", "0.04 mm", "cap separation change, << 7 mm engagement"],
            ["Wind uplift on upper hub (25 m/s)", "~5-10 N", "resisted by set screw in dimple (positive)"]]
    S.table(14, 192, rows, [52, 32, 80], size=6.6)
    y = 150
    S.text(14, y, "OPEN ITEMS / NEEDS PHYSICAL VALIDATION", 8, True)
    S.lines(14, y - 4, [f"- {u}" for u in report["unresolved"]], 6.6)
    S.text(186, 192, "MESH VERIFICATION (trimesh)", 8, True)
    rows = [["STL", "watertight", "bodies", "dV %"]] + [[m["file"][:34], "yes" if m["watertight"] else "NO", m["bodies"], m["volume_error_pct"]] for m in report["meshes"]]
    S.table(186, 189, rows, [50, 13, 9, 12], size=5.4, row_h=3.2)


# ------------------------------------------------------------- templates --
def templates_pdf(P, D, path):
    c = canvas.Canvas(str(path), pagesize=letter)
    W, H = letter
    B = P["blade"]
    segs = FP.outline(P, D)
    an = FP.annotations(P, D)

    def scalebars(y0):
        c.setLineWidth(0.6)
        c.line(20 * mm, y0 * mm, 70 * mm, y0 * mm)
        for k in range(6):
            c.line((20 + 10 * k) * mm, y0 * mm, (20 + 10 * k) * mm, (y0 + (2 if k % 5 else 3.5)) * mm)
        c.setFont("Helvetica", 7)
        c.drawString(20 * mm, (y0 - 4) * mm, "50 mm - measure before cutting")
        c.line(110 * mm, y0 * mm, (110 + 50.8) * mm, y0 * mm)
        c.line(110 * mm, y0 * mm, 110 * mm, (y0 + 3.5) * mm)
        c.line((110 + 50.8) * mm, y0 * mm, (110 + 50.8) * mm, (y0 + 3.5) * mm)
        c.drawString(110 * mm, (y0 - 4) * mm, "2.000 in")

    # page 1: blade flat + formed profile, 1:1
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, H - 14 * mm, "BLADE CUTTING TEMPLATE - 1:1 - PRINT AT 100 % / ACTUAL SIZE (NO FIT-TO-PAGE)")
    c.setFont("Helvetica", 7.5)
    c.drawString(15 * mm, H - 19 * mm, f"1.6 mm aluminium. Blank {B['body_chord']:.2f} x {B['blank_length']:.1f} mm incl. tabs. "
                                         "Cut on the WASTE side of the line (kerf). Cut ONE test blade first.")
    ox, oy = 25, 60

    def T(p):
        return ((ox + p[0]) * mm, (oy + p[1]) * mm)
    c.setLineWidth(0.35)
    pts = FP.polyline_points(segs, 2)
    p = c.beginPath()
    p.moveTo(*T(pts[0]))
    for q in pts[1:]:
        p.lineTo(*T(q))
    p.close()
    c.drawPath(p)
    c.setDash(6, 2)
    c.setStrokeColor(RED)
    c.line(*T((an["tab_centerline_x"], -5)), *T((an["tab_centerline_x"], an["L"] + 5)))
    c.line(*T((-5, an["bow_peak_y"])), *T((an["W"] + 5, an["bow_peak_y"])))
    c.setStrokeColor(Color(0.1, 0.5, 0.1))
    for ys in an["shoulder_y"]:
        c.line(*T((-5, ys)), *T((an["W"] + 5, ys)))
    c.setDash()
    c.setStrokeColor(black)
    c.setFont("Helvetica", 6.5)
    c.drawString(*T((an["W"] + 6, an["shoulder_y"][0] - 1)), "SHOULDER (green) - seats on hub face")
    c.drawString(*T((an["W"] + 6, an["bow_peak_y"] - 1)), "BOW PEAK (red) - mid-length")
    c.drawString(*T((an["W"] + 6, an["shoulder_y"][1] - 1)), "SHOULDER")
    c.drawString(*T((-2, -8)), "INNER EDGE (toward shaft)")
    c.drawString(*T((an["tab_centerline_x"] - 6, -12)), "TAB CENTRELINE")
    c.drawString(*T((4, an["L"] / 2 + 30)), f"W {B['body_chord']:.2f}")
    c.drawString(*T((4, an["L"] / 2 + 25)), f"L {B['blank_length']:.1f}")
    c.drawString(*T((4, an["L"] / 2 + 20)), f"tabs {B['tab_width']:.0f} x {B['tab_length']:.0f}, R2 roots")
    # formed profile
    Hc, s = D["cap_separation"], B["bow_sagitta"]
    px, py = ox + an["W"] + 75, oy + B["tab_length"]
    z = np.linspace(0, Hc, 121)
    w = bow_offset(z, s, Hc)
    c.setStrokeColor(BLUE)
    c.setLineWidth(0.6)
    p = c.beginPath()
    p.moveTo(px * mm, (py - B["tab_length"]) * mm)
    for wv, zv in zip(w, z):
        p.lineTo((px + wv) * mm, (py + zv) * mm)
    p.lineTo(px * mm, (py + Hc + B["tab_length"]) * mm)
    c.drawPath(p)
    c.setStrokeColor(GRAY)
    c.setDash(3, 2)
    c.line(px * mm, (py - B["tab_length"]) * mm, px * mm, (py + Hc + B["tab_length"]) * mm)
    c.setDash()
    c.setStrokeColor(black)
    c.setFont("Helvetica", 6.5)
    c.drawString((px - 12) * mm, (py + Hc + B["tab_length"] + 3) * mm, "FORMED PROFILE GAUGE 1:1")
    c.drawString((px + s + 2) * mm, (py + Hc / 2) * mm, f"{s:.0f} mm")
    c.drawString((px + 2) * mm, (py - 3) * mm, f"shoulders {Hc:.1f} apart")
    scalebars(22)
    c.showPage()

    # page 2: nested stock layout (1:2)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, H - 14 * mm, "NESTED STOCK LAYOUT - 8 BLADES FROM 4 PIECES OF 11.75 x 3.75 in STOCK (SCALE 1:2)")
    k = 0.5
    sl, sw, kerf = 298.45, 95.25, 3.0
    for i in range(4):
        y0 = H / mm - 40 - i * (sw * k + 18)
        c.setLineWidth(0.4)
        c.setDash(5, 2)
        c.rect(20 * mm, (y0 - sw * k) * mm, sl * k * mm, sw * k * mm)
        c.setDash()
        c.setFont("Helvetica", 7)
        c.drawString(20 * mm, (y0 + 2) * mm, f"STOCK {i + 1}  298.45 x 95.25  ->  BLADE {2 * i + 1} + BLADE {2 * i + 2}   (offcut {sw - B['body_chord'] - 4:.1f} mm strip)")
        for j in range(2):
            ox_ = 4 + j * (B["blank_length"] + kerf)
            pts = FP.polyline_points(segs, 6)
            p = c.beginPath()
            q0 = pts[0]
            p.moveTo((20 + (ox_ + q0[1]) * k) * mm, (y0 - sw * k + (4 + q0[0]) * k) * mm)
            for q in pts[1:]:
                p.lineTo((20 + (ox_ + q[1]) * k) * mm, (y0 - sw * k + (4 + q[0]) * k) * mm)
            p.close()
            c.setLineWidth(0.3)
            c.drawPath(p)
    c.setFont("Helvetica", 7.5)
    yt = H / mm - 40 - 4 * (sw * k + 18) + 4
    for t, line in enumerate(["Order of cuts per stock piece: (1) rip the 57.15 mm strip along the full 298.45 length, keeping the",
                              "4 mm edge margin; (2) crosscut at 4 + 139.7 = 143.7 mm, allow 3 mm kerf; (3) crosscut the 2nd blank at",
                              "146.7 + 139.7 = 286.4 mm; (4) notch tabs. The 33 mm offcut strip is ideal for tab-fit test pieces (14 mm wide).",
                              "The CUT DXF (blade_flat_pattern_8x.dxf) carries the same nest at 1:1 for a CNC router or printed paper."]):
        c.drawString(20 * mm, (yt - t * 4) * mm, line)
    c.showPage()

    # page 3: roof cut-out quadrant template 1:1
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, H - 14 * mm, "ROOF CUT-OUT + SCREW TEMPLATE - QUADRANT 1:1 (rotate 4x about the centre mark)")
    S_ = P["stationary"]
    cx, cy = 25 * mm, 40 * mm
    c.setLineWidth(0.5)
    for r, dash, lab in ((S_["throat_id"] / 2, None, "CUT 127 mm (5 in hole saw)"), (S_["flange_od"] / 2, (4, 2), "FLANGE OUTLINE 230"),
                         (S_["flange_screw_circle"] / 2, (1, 2), "SCREW CIRCLE 200")):
        if dash:
            c.setDash(*dash)
        c.arc(cx - r * mm, cy - r * mm, cx + r * mm, cy + r * mm, 0, 90)
        c.setDash()
        c.setFont("Helvetica", 7)
        c.drawString(cx + r * mm * 0.71 + 2 * mm, cy + r * mm * 0.71, lab)
    for kk in range(S_["flange_screw_count"]):
        a = (kk + 0.5) * 2 * math.pi / S_["flange_screw_count"]
        if 0 <= a <= math.pi / 2:
            x, y = cx + S_["flange_screw_circle"] / 2 * math.cos(a) * mm, cy + S_["flange_screw_circle"] / 2 * math.sin(a) * mm
            c.circle(x, y, S_["flange_screw_hole"] / 2 * mm)
            c.line(x - 3 * mm, y, x + 3 * mm, y)
            c.line(x, y - 3 * mm, x, y + 3 * mm)
    c.line(cx - 5 * mm, cy, cx + 120 * mm, cy)
    c.line(cx, cy - 5 * mm, cx, cy + 120 * mm)
    c.drawString(cx + 2 * mm, cy - 4 * mm, "CENTRE (rotor axis)  - align X line with roof slope (uphill = +X)")
    scalebars(20)
    c.showPage()
    c.save()


# ---------------------------------------------------------------- single-page PDFs
def simple_pdf(path, title, images, lines):
    c = canvas.Canvas(str(path), pagesize=landscape(letter))
    S = Sheet(c, title)
    S.text(14, 200, title, 11, True)
    n = len(images)
    w = (255 - 6 * (n - 1)) / n
    for k, (img, lab) in enumerate(images):
        S.image(img, 12 + k * (w + 6), 60, w, 130)
        S.text(12 + k * (w + 6), 56, lab, 7.5, True)
    S.lines(12, 48, lines, 7.5)
    S.frame(1, 1)
    c.showPage()
    c.save()


def comparison_pdf(path, P, D, renders, study_rows):
    c = canvas.Canvas(str(path), pagesize=landscape(letter))
    S = Sheet(c, "8 / 10 / 12 blade comparison (real CAD)")
    S.text(14, 200, "8 / 10 / 12 BLADE COMPARISON - SAME BLADE, SAME HUBS (real CAD renders)", 11, True)
    for k, n in enumerate((8, 10, 12)):
        S.image(renders / f"compare_{n}_blades_iso.png", 12 + k * 86, 128, 82, 66)
        S.image(renders / f"compare_{n}_blades_top_no_cap.png", 12 + k * 86, 64, 82, 62)
    rows = [["Blades", "Chord deg", "Bow", "Rotor OD", "Blade gap", "Plan coverage %", "Blade set g", "Height"]]
    for r in study_rows:
        if r["chord_angle_deg"] == P["blade"]["plan_chord_angle_from_radial"] and r["bow_sagitta_mm"] == P["blade"]["bow_sagitta"]:
            rows.append([r["blades"], r["chord_angle_deg"], r["bow_sagitta_mm"], r["rotor_od_mm"], r["neighbour_clearance_mm"],
                         r["plan_coverage_pct"], r["blade_set_mass_g"], r["installed_height_mm"]])
    S.table(12, 60, rows, [16, 18, 12, 20, 20, 26, 22, 18], size=7)
    S.lines(172, 60, ["Reading the table:", "- No collisions for 8, 10 or 12 with this blade envelope.",
                      "- More blades raise plan coverage (rain shading) and mass,", "  and reduce the open exhaust area between blades.",
                      "- They do NOT guarantee more ventilation or rain-tightness.", "- 8 blades remains the primary design; 10/12 are",
                      "  parametric (set blade_count) pending airflow tests.", "- Full 27-variant table: whirlybird/reports/variant_study.csv"], 7.2)
    S.frame(1, 2)
    c.showPage()
    S2 = Sheet(c, "Chord angle variants")
    S2.text(14, 200, "PLAN CHORD ANGLE VARIANTS 25 / 35 / 45 deg (8 blades, upper hub hidden)", 11, True)
    for k, th in enumerate((25, 35, 45)):
        S2.image(renders / f"compare_chord_{th}deg_top.png", 12 + k * 86, 90, 82, 100)
    rows = [["Chord deg", "Bow 10: OD / cov%", "Bow 15: OD / cov%", "Bow 20: OD / cov%", "Gap mm"]]
    for th in (25, 35, 45):
        rr = [r for r in study_rows if r["blades"] == 8 and r["chord_angle_deg"] == th]
        rows.append([th] + [f"{r['rotor_od_mm']} / {r['plan_coverage_pct']}" for r in rr] + [rr[0]["neighbour_clearance_mm"]])
    S2.table(12, 84, rows, [22, 40, 40, 40, 18], size=7.5)
    S2.lines(12, 60, ["Selected: 35 deg, 15 mm bow - OD within the 254-279 mm window, 50 mm blade gaps, 49.6 mm minimum bend radius",
                      "(easy to press-form 1.6 mm aluminium). 20 mm bow gives ~5 mm more OD but a 35 mm bend radius and more springback.",
                      "45 deg gives the most plan coverage but the smallest OD. No variant is claimed aerodynamically optimal."], 7.5)
    S2.frame(2, 2)
    c.showPage()
    c.save()


def make_all(P, D, items, report, DIRS):
    renders, pdf = DIRS["renders"], DIRS["pdf"]
    path = pdf / "fabrication_drawings.pdf"
    c = canvas.Canvas(str(path), pagesize=landscape(letter))
    total = 12
    makers = [
        ("Cover, datums, results", lambda S: sheet_cover(S, P, D, report, renders), "NTS"),
        ("Axial section, height stack", lambda S: sheet_section(S, P, D, items, renders), "1:2"),
        ("Rotor vs stationary", lambda S: sheet_rotor_stator(S, P, D, items, renders), "NTS"),
        ("Exploded assembly", lambda S: sheet_exploded(S, P, D, renders), "NTS"),
        ("True CAD views", lambda S: sheet_views(S, renders), "NTS"),
        ("Upper hub", lambda S: _hub_sheet(S, P, D, next(i.shape for i in items if i.name == "upper_hub_closed_top"), "upper_hub_closed_top", renders, True), "1:2"),
        ("Lower hub", lambda S: _hub_sheet(S, P, D, next(i.shape for i in items if i.name == "lower_hub_closed_bottom"), "lower_hub_closed_bottom", renders, False), "1:2"),
        ("Bearing support", lambda S: sheet_support(S, P, D, items, renders), "1:1"),
        ("Roof flash adapter", lambda S: sheet_adapter(S, P, D, items, report, renders), "1:1.67"),
        ("Blade", lambda S: sheet_blade(S, P, D, report, renders), "1:1"),
        ("Coupons + tooling", lambda S: sheet_coupons(S, P, renders), "NTS"),
        ("Checks + calcs", lambda S: sheet_checks(S, P, D, report), "NTS"),
    ]
    for k, (title, fn, scale) in enumerate(makers):
        S = Sheet(c, title, scale)
        fn(S)
        S.frame(k + 1, total)
        c.showPage()
    c.save()

    # stand-alone PDFs named in the spec
    c = canvas.Canvas(str(pdf / "assembly_section.pdf"), pagesize=landscape(letter))
    S = Sheet(c, "Axial section", "1:2")
    sheet_section(S, P, D, items, renders)
    S.frame(1, 2)
    c.showPage()
    S = Sheet(c, "Blind pocket sections", "NTS")
    S.text(14, 200, "BLIND POCKET SECTIONS - plane along blade-1 chord through the tab centre (true CAD)", 10, True)
    S.image(renders / "pocket_section_upper.png", 12, 70, 126, 120)
    S.image(renders / "pocket_section_lower.png", 144, 70, 126, 120)
    S.text(12, 66, "UPPER HUB: pocket opens DOWN only; 3.5 mm intact roof; closed toward OD", 7.5, True)
    S.text(144, 66, "LOWER HUB: pocket opens UP only; 3.5 mm floor; diamond weep to OD", 7.5, True)
    S.lines(12, 58, [f"Tab 1.60 in pocket {P['pocket']['width']:.2f}: {(P['pocket']['width'] - 1.6) / 2:.3f} mm per side.  "
                     f"Tab 14.0 in pocket {D['pocket_length']:.1f}: 0.25 mm per end.  Tip to floor {D['tab_bottom_clearance_in_pocket']:.1f} mm.",
                     "Mouth: 2 x 45 deg end lead-in clears the R2 tab-root fillets; 0.5 mm side lead-in guides the tab.",
                     "Retention: shoulders seat on the hub faces (axial); closed pocket ends/sides (radial + tangential); hubs fixed",
                     "to the shaft by set screws in drilled dimples (positive) - so blades cannot escape without removing a hub."], 7.5)
    S.frame(2, 2)
    c.showPage()
    c.save()
    c = canvas.Canvas(str(pdf / "assembly_exploded.pdf"), pagesize=landscape(letter))
    S = Sheet(c, "Exploded assembly")
    sheet_exploded(S, P, D, renders)
    S.frame(1, 1)
    c.showPage()
    c.save()
    c = canvas.Canvas(str(pdf / "rotor_vs_stationary.pdf"), pagesize=landscape(letter))
    S = Sheet(c, "Rotor vs stationary")
    sheet_rotor_stator(S, P, D, items, renders)
    S.frame(1, 1)
    c.showPage()
    c.save()
    simple_pdf(pdf / "CAD_views_top_side_underside.pdf", "TRUE CAD-RENDERED VIEWS: TOP / SIDE / UNDERSIDE",
               [(renders / "view_top.png", "TOP"), (renders / "view_side.png", "SIDE"), (renders / "view_underside.png", "UNDERSIDE")],
               ["Orthographic renders of the tessellated build123d solids (no artistic imagery).",
                "Orange = printed rotating hubs; silver = aluminium blades; grey-blue = stationary roof parts; green = optional drip tray."])
    templates_pdf(P, D, DIRS["templates"] / "blade_and_roof_templates_1to1.pdf")
    import csv
    with open(DIRS["reports"] / "variant_study.csv") as f:
        rows = [{k: (float(v) if v.replace('.', '', 1).replace('-', '', 1).isdigit() else v) for k, v in r.items()} for r in csv.DictReader(f)]
    for r in rows:
        for k in ("blades", "chord_angle_deg", "bow_sagitta_mm"):
            r[k] = int(r[k])
    comparison_pdf(pdf / "comparison_8_10_12_blades.pdf", P, D, renders, rows)
