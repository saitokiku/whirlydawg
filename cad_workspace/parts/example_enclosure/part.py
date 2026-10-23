# Example: open-top enclosure tray. Edit PARAMS, rerun; never hardcode numbers below.
# Units: mm. Datum: origin at bottom-centre of the part, +Z up.
PARAMS = dict(
    length=60.0,        # X
    width=40.0,         # Y
    height=20.0,        # Z
    wall=2.0,
    floor=2.0,
    corner_r=3.0,       # vertical-edge fillet (applied before shelling)
    mount_hole_d=3.4,   # M3 clearance
    mount_inset=6.0,    # hole centre from outer edge
)
p = PARAMS

body = Box(p["length"], p["width"], p["height"], align=(Align.CENTER, Align.CENTER, Align.MIN))
body = fillet(body.edges().filter_by(Axis.Z), p["corner_r"])
cavity = Box(p["length"] - 2*p["wall"], p["width"] - 2*p["wall"], p["height"],
             align=(Align.CENTER, Align.CENTER, Align.MIN)).translate((0, 0, p["floor"]))
cavity = fillet(cavity.edges().filter_by(Axis.Z), max(p["corner_r"] - p["wall"], 0.5))
part = body - cavity

# four mounting holes through the floor
for sx in (-1, 1):
    for sy in (-1, 1):
        x = sx * (p["length"]/2 - p["mount_inset"])
        y = sy * (p["width"]/2 - p["mount_inset"])
        part -= Pos(x, y, 0) * Cylinder(p["mount_hole_d"]/2, p["floor"]*3,
                                         align=(Align.CENTER, Align.CENTER, Align.MIN))
show_object(part)
