"""Regenerate the complete whirlybird CAD package from MASTER_PARAMETERS.json.

    cd whirlybird/cad
    xvfb-run -a python build_all.py            # everything (renders need a display)
    python build_all.py --no-render --no-pdf   # CAD + checks + meshes only
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import trimesh  # noqa: E402
from build123d import Color, Compound, export_step, export_stl  # noqa: E402

import assembly as A  # noqa: E402
import checks as C  # noqa: E402
import flatpattern as FP  # noqa: E402
import geometry as g  # noqa: E402
from params import derive, load_inputs, variant, write_report, unresolved  # noqa: E402

import layout as L  # noqa: E402

DIRS = L.DIRS

RGB = {"rotor": (0.93, 0.55, 0.20), "blade": (0.78, 0.80, 0.83), "shaft": (0.45, 0.47, 0.50),
       "hardware": (0.25, 0.25, 0.28), "bearing": (0.30, 0.55, 0.85), "stator": (0.55, 0.60, 0.66),
       "adapter": (0.42, 0.46, 0.52), "tray": (0.35, 0.65, 0.55), "tool": (0.60, 0.40, 0.75)}

PITCHES = {"0in12": 0.0, "2in12": math.degrees(math.atan(2 / 12)), "3in12": math.degrees(math.atan(3 / 12)),
           "4in12": math.degrees(math.atan(4 / 12)), "5in12": math.degrees(math.atan(5 / 12))}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def colored(shape, key, label):
    s = shape
    s.label = label
    s.color = Color(*RGB[key])
    return s


def export_mesh(shape, path, cad_volume, bed, margin):
    export_stl(shape, str(path), tolerance=0.02, angular_tolerance=0.12)
    m = trimesh.load_mesh(str(path), process=True)
    bodies = m.split(only_watertight=False)
    ext = m.bounds[1] - m.bounds[0]
    rep = {
        "file": path.name,
        "triangles": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "is_volume": bool(m.is_volume),
        "bodies": int(len(bodies)),
        "euler_number": int(m.euler_number),
        "mesh_volume_mm3": round(float(m.volume), 1),
        "cad_volume_mm3": round(float(cad_volume), 1),
        "volume_error_pct": round(100 * (float(m.volume) - cad_volume) / cad_volume, 3),
        "extent_mm": [round(float(e), 2) for e in ext],
        "min_z": round(float(m.bounds[0][2]), 4),
        "fits_bed": bool(ext[0] <= bed[0] - 2 * margin and ext[1] <= bed[1] - 2 * margin and ext[2] <= bed[2]),
    }
    # printability: downward-facing area steeper than 45 deg that is NOT on the bed (bridges + overhangs)
    import numpy as _np
    nz = m.face_normals[:, 2]
    cz = m.triangles_center[:, 2] - m.bounds[0][2]
    down = (nz < -0.7071) & (cz > 0.3)
    rep["unsupported_down_area_mm2"] = round(float(m.area_faces[down].sum()), 1)
    rep["unsupported_max_height_mm"] = round(float(cz[down].max()), 1) if down.any() else 0.0
    rep["pass"] = (rep["watertight"] and rep["winding_consistent"] and rep["is_volume"] and rep["bodies"] == 1
                   and abs(rep["volume_error_pct"]) < 1.0 and rep["fits_bed"] and abs(rep["min_z"]) < 0.01)
    return rep


def build(args):
    for d in L.ALL:
        d.mkdir(parents=True, exist_ok=True)
    P = load_inputs()
    D = derive(P)
    write_report(P, D)
    log(f"derived: H={D['cap_separation']:.2f} height={D['installed_height']:.1f} OD={D['rotor_od_actual']:.1f}")

    import study
    study.main(verbose=False)
    items = A.build(P, D)
    report = {"inputs_file": "MASTER_PARAMETERS.json", "derived_summary": {}}
    gates = []

    def gate(name, ok, value):
        gates.append({"gate": name, "pass": bool(ok), "value": value})

    # ---------------------------------------------------------------- checks --
    log("checks: interference")
    inter = C.interference(items)
    bad = [r for r in inter if not r[3]]
    gate("No unintended solid interference anywhere in the assembly", not bad,
         [f"{a} x {b}: {v:.3f} mm3" for a, b, v, ok in inter])
    log("checks: rotor/stator clearance")
    rs = C.rotor_stator_clearance(items)
    rs_real = [r for r in rs if not ("race" in r[0] or "seal" in r[1] or "race" in r[1])]
    gate("Rotating parts never touch stationary parts (min clearance >= 1.5 mm, excl. bearing internals)",
         min(r[2] for r in rs_real) >= 1.5, [f"{a} / {b}: {d:.2f}" for a, b, d in rs_real[:10]])
    lh_gap = D["z_lower_hub_bottom"] - D["z_collar_top"]
    gate("Lower hub face to stationary collar/support axial gap = 6 mm", abs(lh_gap - 6.0) < 1e-6, lh_gap)
    log("checks: blades")
    nb, brow = C.blade_clearances(items, P)
    gate("Blade-to-blade clearance (no collision incl. bow)", nb > 5.0, round(nb, 2))
    gate("Blade-to-stationary clearance", min(r[2] for r in brow) > 5.0, [f"{a}/{b}: {d:.1f}" for a, b, d in brow])
    tp = C.tab_in_pocket(P, D)
    gate("Tab fits pocket with clearance on all sides and does not bottom out",
         tp["side_clearance_each_side"] > 0 and tp["end_clearance_each_end"] > 0 and tp["tab_tip_to_pocket_bottom"] > 0.5, tp)
    log("checks: blind pockets")
    pb = C.pocket_blindness(items, P, D)
    minshell = P["pocket"]["min_exterior_shell"]
    gate("Upper hub top face is one closed plane (no pocket breaks through)",
         pb["upper_top_face_count"] == 1 and pb["upper_top_face_holes"] == 0, pb)
    gate(f"Pocket walls to every exterior face >= {minshell} mm (top/bottom/OD)",
         min(pb["upper_pocket_to_top_face"], pb["upper_pocket_to_OD"], pb["lower_pocket_to_bottom_face"],
             pb["lower_pocket_to_OD_excluding_weep"]) >= minshell - 1e-6,
         {k: round(v, 3) for k, v in pb.items() if isinstance(v, float)})
    log("checks: access + assembly sequence")
    ac = C.access_check(items, P, D)
    gate("Hex-key access to both hub set screws through blade gaps",
         min(ac["upper_key_path_min_clearance_to_blades"], ac["lower_key_path_min_clearance_to_blades"]) > 2.0, ac)
    seq = C.assembly_sequence(P, D, items)
    free = [s for s in seq if "should COLLIDE" not in s[0]]
    trap = [s for s in seq if "should COLLIDE" in s[0]]
    gate("Assembly sequence collision-free (blades drop into lower hub, upper hub drops over tabs)",
         all(v < 1e-3 for _, v in free), [(n, round(v, 4)) for n, v in free])
    gate("Blades positively trapped once hubs are fixed (axial + radial)", all(v > 0.1 for _, v in trap),
         [(n, round(v, 2)) for n, v in trap])
    gate(f"Installed height <= {P['max_installed_height']} mm", D["installed_height"] <= P["max_installed_height"],
         round(D["installed_height"], 2))
    bbz = max(it.shape.bounding_box().max.Z for it in items)
    gate("Assembly CAD top equals reported installed height", abs(bbz - D["installed_height"]) < 0.01, round(bbz, 3))
    rc = C.roof_clearance(items, P, D)
    gate("Rotor clears roof surface by >= 6 mm (at modelled pitch)", rc["min"] >= 6.0, rc)
    bf = C.bed_fit(items, P)
    gate("Every printed part fits the X1E bed in print orientation", all(r[3] for r in bf),
         [(n, [round(x, 1) for x in sz]) for n, sz, z, ok in bf])
    gate("Shaft length fits user's 209.55 mm tube (if bearings accept it)", D["shaft_fits_user_tube_length"],
         round(D["shaft_length"], 2))
    report["gates"] = gates
    for gg in gates:
        log(f"  {'PASS' if gg['pass'] else 'FAIL'}  {gg['gate']}")

    # --------------------------------------------------------------- exports --
    log("export STEP")
    kids = []
    for it in items:
        kids.append(colored(it.shape, it.color, it.name))
    asm = Compound(children=kids, label="whirlybird_complete_assembly")
    export_step(asm, str(DIRS["step"] / "whirlybird_complete_assembly.step"))
    rot = Compound(children=[colored(it.shape, it.color, it.name) for it in items if "rotating" in it.role], label="rotor")
    export_step(rot, str(DIRS["step"] / "rotor_subassembly.step"))
    for it in items:
        if it.printable or it.name in ("blade_1", "shaft"):
            fname = "blade_formed.step" if it.name == "blade_1" else f"{it.name}.step"
            export_step(colored(it.shape, it.color, it.name), str(DIRS["step"] / fname))

    # tooling, coupons, extras
    extras = {}
    lower_die, upper_die, s_die, H_die = g.forming_dies(P, D)
    extras["blade_forming_die_lower"] = (lower_die, lambda s: A.on_bed(s))
    extras["blade_forming_die_upper"] = (upper_die, lambda s: A.on_bed(s, flip=True))
    extras["single_blade_socket_test_top"] = (g.socket_coupon(P, D, "top"), lambda s: A.on_bed(s, flip=True))
    extras["single_blade_socket_test_bottom"] = (g.socket_coupon(P, D, "bottom"), lambda s: A.on_bed(s))
    extras["slot_clearance_coupon_1p85_1p95_2p05_2p15"] = (g.slot_width_coupon(P, D), lambda s: A.on_bed(s))
    extras["bearing_and_shaft_fit_coupon"] = (g.fit_coupon(P), lambda s: A.on_bed(s))
    extras["shaft_dimple_drill_guide"] = (g.drill_guide(P), lambda s: A.on_bed(s))
    extras["inlet_vent_louver"] = (g.inlet_louver(P), lambda s: A.on_bed(s))
    extras["lower_hub_SOLID_DISC_ALTERNATE_not_recommended"] = (g.lower_hub(P, D, solid_variant=True), lambda s: A.on_bed(s))
    report["forming_die"] = {"die_sagitta": round(s_die, 2), "die_cap_separation": round(H_die, 2),
                             "springback_factor": P["forming_die"]["springback_factor"]}
    for name, (shape, _) in extras.items():
        export_step(colored(shape, "tool" if "die" in name or "guide" in name else "rotor", name), str(DIRS["step"] / f"{name}.step"))

    # roof adapter variants for unknown pitch
    pitch_rows = []
    for tag, deg in PITCHES.items():
        Q = variant(P, roof_pitch_deg=deg)
        DQ = derive(Q)
        ad = g.roof_adapter(Q, DQ)
        extras[f"roof_flash_adapter_pitch_{tag}"] = (ad, (lambda Qc: (lambda s: A.on_bed_roof(s, Qc)))(Q))
        export_step(colored(ad, "adapter", f"roof_flash_adapter_pitch_{tag}"), str(DIRS["step"] / f"roof_flash_adapter_pitch_{tag}.step"))
        pitch_rows.append({"pitch": tag, "deg": round(deg, 2), "collar_top_at_axis": round(DQ["z_collar_top"], 1),
                           "installed_height": round(DQ["installed_height"], 1),
                           "within_190p5": DQ["installed_height"] <= P["max_installed_height"],
                           "roof_clearance_min": round(C.roof_clearance([], Q, DQ)["min"], 1)})
    report["roof_pitch_table"] = pitch_rows

    log("export + validate STL")
    bed, margin = P["printer"]["bed"], P["printer"]["bed_margin"]
    meshes = []
    for it in items:
        if not it.printable:
            continue
        s = it.print_pose(it.shape)
        if L.stl_dir(it.name) is not None:
            meshes.append(export_mesh(s, L.stl_dir(it.name) / f"{it.name}.stl", it.shape.volume, bed, margin))
    for name, (shape, pose) in extras.items():
        s = pose(shape)
        meshes.append(export_mesh(s, L.stl_dir(name) / f"{name}.stl", shape.volume, bed, margin))
    report["meshes"] = meshes
    gate("All STL meshes watertight, manifold, single body, volume within 1 %, on bed",
         all(m["pass"] for m in meshes), [m["file"] for m in meshes if not m["pass"]])
    for m in meshes:
        log(f"  {'ok ' if m['pass'] else 'BAD'} {m['file']:60s} tris={m['triangles']:7d} dV={m['volume_error_pct']:+.3f}% ext={m['extent_mm']}")

    log("flat patterns")
    FP.write_dxf(P, D, DIRS["dxf"] / "blade_flat_pattern_single_TEST.dxf", "single")
    FP.write_dxf(P, D, DIRS["dxf"] / "blade_flat_pattern_8x.dxf", "batch")
    FP.svg_blade(P, D, DIRS["svg"] / "blade_template_1to1.svg")

    # mass / filament estimate (PETG 1.27, PAHT-CF 1.2 g/cm3; ~55 % effective fill for 5 walls + 40 % infill)
    fil = []
    for it in items:
        if it.printable:
            fil.append((it.name, round(it.shape.volume / 1000 * 1.27 * 0.55 + 0.0, 1)))
    report["filament_estimate_g_PETG"] = fil
    report["derived_summary"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in D.items()
                                 if not isinstance(v, (dict, list))}
    report["unresolved"] = unresolved(P, D)
    report["all_gates_pass"] = all(gg["pass"] for gg in gates)
    with open(DIRS["reports"] / "design_checks.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    write_mesh_log(meshes, DIRS["reports"] / "mesh_verification_log.txt")
    write_bom(P, D, items, fil, L.BOM)

    if args.render:
        log("renders")
        import views
        views.make_all(P, D, items, DIRS["renders"], extras)
    if args.pdf:
        log("pdf drawings")
        import drawings
        drawings.make_all(P, D, items, report, DIRS)
    log(f"ALL GATES PASS = {report['all_gates_pass']}")
    return report


def write_mesh_log(meshes, path):
    with open(path, "w") as f:
        f.write("STL MESH VERIFICATION LOG (trimesh %s)\n" % trimesh.__version__)
        f.write("Criteria: watertight, consistent winding, positive volume, exactly 1 body, |mesh-CAD volume| < 1 %,\n"
                "          extent within 250 x 250 x 256 mm (3 mm bed margin), lowest point on z = 0 (print pose).\n\n")
        for m in meshes:
            f.write(f"{'PASS' if m['pass'] else 'FAIL'}  {m['file']}\n")
            for k, v in m.items():
                if k not in ("file", "pass"):
                    f.write(f"      {k:22s} {v}\n")
        f.write(f"\nOVERALL: {'PASS' if all(m['pass'] for m in meshes) else 'FAIL'} ({len(meshes)} files)\n")


def write_bom(P, D, items, fil, path):
    fil = dict(fil)
    rows = [
        ["item", "qty", "type", "spec / size", "material", "est_filament_g", "source", "notes"],
        ["upper_hub_closed_top", 1, "printed, rotating", "OD %.0f, 8 blind pockets open DOWN, closed top, drip lip" % P["upper_hub"]["od"],
         "PAHT-CF final (PETG-HF trial)", fil.get("upper_hub_closed_top"), "print", "top face down on bed"],
        ["lower_hub_closed_bottom", 1, "printed, rotating", "OD %.0f, 8 blind pockets open UP, weeps, chimney, labyrinth cup" % P["lower_hub"]["od"],
         "PAHT-CF final (PETG-HF trial)", fil.get("lower_hub_closed_bottom"), "print", "bottom down on bed"],
        ["blade", P["blade_count"], "sheet metal, rotating", "%.2f x %.1f blank, tabs %.0f x %.0f, bow %.0f mm" % (
            P["blade"]["body_chord"], P["blade"]["blank_length"], P["blade"]["tab_width"], P["blade"]["tab_length"], P["blade"]["bow_sagitta"]),
         "1.6 mm aluminium", "", "OWNED stock (4 pieces 11.75 x 3.75 in)", "cut 1 test blade first"],
        ["shaft", 1, "rotating", "6.35 mm (1/4 in) x %.1f mm" % D["shaft_length"], "303/304 stainless precision rod", "",
         "BUY (or OWNED tube if it slips into bearings)", "2 spot dimples for set screws"],
        ["bearing R4-2RS", 2, "stationary outer / rotating inner", "6.35 x 15.875 x 4.98", "steel, sealed", "", "OWNED", "verify bore marking"],
        ["shaft collar 1/4 in bore", 1, "rotating", "OD ~12.7, width ~7.9, set screw", "steel / stainless", "", "BUY", "below lower bearing"],
        ["set screw M4 x 6 cup point", 2, "rotating", "A2 stainless + medium threadlocker", "stainless", "", "BUY", "one per hub, into shaft dimple"],
        ["hex nut M4 DIN 934", 2, "rotating", "7 AF x 3.2", "stainless", "", "BUY", "drops into hub nut slot"],
        ["thrust_washer_top / bottom", 2, "printed, rotating", "OD %.1f ID 6.5, t 2.0 / 1.5" % P["bearings"]["inner_race_land_od"],
         "PETG-HF", round((fil.get("thrust_washer_top") or 0) + (fil.get("thrust_washer_bottom") or 0), 1), "print",
         "contacts bearing INNER race only"],
        ["bearing_support_stationary", 1, "printed, stationary", "ring + 3 spokes + 2-bearing tower, 50 mm bearing spacing",
         "PAHT-CF or ABS (painted)", fil.get("bearing_support_stationary"), "print", ""],
        ["roof_flash_adapter (pick pitch file)", 1, "printed, stationary", "flange OD 230, collar, gasket groove, 8 screw holes",
         "ABS (painted) or PAHT-CF", fil.get("roof_flash_adapter"), "print", "choose STL matching roof pitch"],
        ["M3 x 12 pan screw, stainless", 3, "stationary", "support ring to adapter collar (self-tapping into printed boss)", "stainless", "", "BUY", ""],
        ["#8 x 3/4 in pan-head wood screw + EPDM/neoprene washer", 8, "stationary", "adapter flange to roof deck", "stainless", "", "BUY", ""],
        ["exterior sealant (butyl tape or polyurethane / silicone)", 1, "stationary", "bead in flange gasket groove + screw heads", "", "", "BUY", ""],
        ["rain_baffle_if_needed", 1, "printed, stationary (optional)", "150 mm drip tray clipped to tower bottom, 6.4 mm drain hole", "PETG-HF",
         fil.get("rain_baffle_if_needed"), "print if water test fails", "+1 M3 x 10 clamp screw; optional 1/4 in OD vinyl drain tube pressed into hole"],
        ["inlet_vent_louver", 2, "printed, stationary", "170 x 120 frame, 140 x 90 opening, 45 deg louvres", "PETG-HF / ABS", "~45 each", "print",
         "+ aluminium/fibreglass insect screen 150 x 100, 4 screws each"],
        ["blade_forming_die_lower / upper", 1, "tool", "press in bench vise", "PETG-HF or PLA, 6 walls 50 % infill", "~190", "print", ""],
        ["single_blade_socket_test_top / bottom", 1, "test coupon", "one pocket each", "PETG-HF or PLA", "~10", "print FIRST", ""],
        ["slot_clearance_coupon", 1, "test coupon", "1.85 / 1.95 / 2.05 / 2.15 mm", "same as final hubs", "~30", "print FIRST", ""],
        ["bearing_and_shaft_fit_coupon", 1, "test coupon", "seats 15.80-16.10, bores 6.45-6.65", "same as final hubs", "~25", "print FIRST", ""],
        ["shaft_dimple_drill_guide", 1, "tool", "3.5 mm spot drill guide on 1/4 in rod", "PETG-HF", "~15", "print", ""],
    ]
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", dest="render", action="store_false")
    ap.add_argument("--no-pdf", dest="pdf", action="store_false")
    a = ap.parse_args()
    r = build(a)
    sys.exit(0 if r["all_gates_pass"] else 1)
