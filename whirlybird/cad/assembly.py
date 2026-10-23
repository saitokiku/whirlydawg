"""Assembly definition: every part, its role (rotating / stationary), colour and print pose."""
from __future__ import annotations

from dataclasses import dataclass, field

from build123d import Compound, Location, Part, Pos, Rot, mirror, Plane

import geometry as g


@dataclass
class Item:
    name: str
    shape: Part
    role: str            # "rotating" | "stationary" | "purchased-rotating" | "purchased-stationary"
    color: str
    qty: int = 1
    printable: bool = False
    material: str = ""
    print_pose: object = None   # callable(shape) -> shape on bed (z>=0)
    notes: str = ""
    explode: float = 0.0        # Z offset in exploded view
    group: str = ""             # name used to group repeated items (blades)


def on_bed(shape, flip=False):
    s = mirror(shape, Plane.XY) if flip else shape
    bb = s.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * s


def build(P, D, include_tray=True):
    items: list[Item] = []
    N = P["blade_count"]
    H = D["cap_separation"]

    uh = g.upper_hub(P, D)
    items.append(Item("upper_hub_closed_top", uh, "rotating", "rotor", printable=True,
                      material="PAHT-CF (final) / PETG-HF (fit trial)",
                      print_pose=lambda s: on_bed(s, flip=True), explode=95,
                      notes="Print top-face DOWN (closed top on bed); pockets print as open slots."))
    lh = g.lower_hub(P, D)
    items.append(Item("lower_hub_closed_bottom", lh, "rotating", "rotor", printable=True,
                      material="PAHT-CF (final) / PETG-HF (fit trial)",
                      print_pose=lambda s: on_bed(s), explode=0,
                      notes="Print closed bottom DOWN; pockets open up; 28 mm cup ceiling bridges."))
    for i in range(N):
        items.append(Item(f"blade_{i + 1}", g.blade(i, P, D), "rotating", "blade",
                          material="1.6 mm aluminium sheet", explode=45, group="blade"))
    items.append(Item("shaft", g.shaft(P, D), "purchased-rotating", "shaft",
                      material="1/4 in (6.35 mm) stainless rod, or user tube if it fits the bearings",
                      explode=-60))
    wt, wb = g.washers(P, D)
    items.append(Item("thrust_washer_top", wt, "rotating", "hardware", printable=True,
                      material="PETG-HF", print_pose=lambda s: on_bed(s), explode=-8))
    items.append(Item("thrust_washer_bottom", wb, "rotating", "hardware", printable=True,
                      material="PETG-HF", print_pose=lambda s: on_bed(s), explode=-75))
    items.append(Item("shaft_collar", g.shaft_collar(P, D), "purchased-rotating", "hardware",
                      material="1/4 in bore set-screw shaft collar", explode=-85))
    for tag, z in (("upper", D["z_upper_set_screw"]), ("lower", D["z_lower_set_screw"])):
        nut, screw = g.nut_and_screw(P, D, z, tag == "upper")
        ex = 95 if tag == "upper" else 0
        items.append(Item(f"{tag}_hub_nut_M4", nut, "purchased-rotating", "hardware", explode=ex))
        items.append(Item(f"{tag}_hub_set_screw_M4", screw, "purchased-rotating", "hardware", explode=ex))
    for tag, zc in (("upper", D["z_upper_bearing_center"]), ("lower", D["z_lower_bearing_center"])):
        inner, outer, seal = g.bearing(P, zc)
        items.append(Item(f"bearing_{tag}_inner_race", inner, "purchased-rotating", "bearing", explode=-30))
        items.append(Item(f"bearing_{tag}_outer_race", outer, "purchased-stationary", "bearing", explode=-30))
        items.append(Item(f"bearing_{tag}_seal", seal, "purchased-stationary", "bearing", explode=-30))
    items.append(Item("bearing_support_stationary", g.bearing_support(P, D), "stationary", "stator",
                      printable=True, material="PAHT-CF or ABS (painted)", explode=-30,
                      print_pose=lambda s: on_bed(s, flip=True),
                      notes="Print TOWER-TOP DOWN; tree supports (build plate only) under ring + spokes, 12 mm tall."))
    items.append(Item("roof_flash_adapter", g.roof_adapter(P, D), "stationary", "adapter",
                      printable=True, material="ABS (painted) or PAHT-CF", explode=-110,
                      print_pose=lambda s: on_bed_roof(s, P),
                      notes="Print roof-contact face DOWN."))
    if include_tray:
        items.append(Item("rain_baffle_if_needed", g.rain_tray(P, D), "stationary", "tray",
                          printable=True, material="PETG-HF", explode=-140,
                          print_pose=lambda s: on_bed(s),
                          notes="Optional drip tray under the throat, inside the doghouse."))
    return items


def on_bed_roof(shape, P):
    import math
    p = P["roof_pitch_deg"]
    s = Rot(0, p, 0) * shape if p else shape
    if p:
        s = Rot(0, 0, 45) * s    # long axis of the tilted collar goes across the bed diagonal
    bb = s.bounding_box()
    return Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * s


def compound(items, explode=False, roles=None):
    kids = []
    for it in items:
        if roles and it.role not in roles:
            continue
        s = Pos(0, 0, it.explode) * it.shape if explode else it.shape
        s = s.moved(Location()) if hasattr(s, "moved") else s
        s.label = it.name
        kids.append(s)
    return Compound(children=kids, label="whirlybird_assembly")
