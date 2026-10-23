"""Independent validation of the exported STEP files with the agentcad CLI.

Runs `agentcad inspect` (kernel / shell / manifold validity) on every STEP and
`agentcad check-spec` on the parts with explicit cylindrical requirements.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from params import derive, load_inputs  # noqa: E402

import layout as L  # noqa: E402

STEP = L.STEP
REP = L.REPORTS
SPEC = L.REPORTS / "specs"


def run(args):
    r = subprocess.run(["agentcad", *args], capture_output=True, text=True)
    out = r.stdout
    return json.loads(out[out.index("{"):]) if "{" in out else {"error": r.stderr[-500:]}


def main():
    P = load_inputs()
    D = derive(P)
    SPEC.mkdir(parents=True, exist_ok=True)
    tol = 0.06
    bore = P["shaft"]["hub_bore_diameter"]
    specs = {
        "upper_hub_closed_top": {"expect_solids": 1, "features": [
            {"name": "shaft_bore_blind", "type": "cylinder", "diameter_mm": bore, "diameter_tolerance_mm": tol, "count": 1},
            {"name": "set_screw_hole", "type": "cylinder", "diameter_mm": P["hub_fixing"]["screw_hole_diameter"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "outer_diameter", "type": "cylinder", "diameter_mm": P["upper_hub"]["od"], "diameter_tolerance_mm": tol, "count": 1}]},
        "lower_hub_closed_bottom": {"expect_solids": 1, "features": [
            {"name": "shaft_bore", "type": "cylinder", "diameter_mm": bore, "diameter_tolerance_mm": tol, "count": 1},
            {"name": "set_screw_hole", "type": "cylinder", "diameter_mm": P["hub_fixing"]["screw_hole_diameter"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "chimney_id", "type": "cylinder", "diameter_mm": P["lower_hub"]["chimney_id"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "labyrinth_cup", "type": "cylinder", "diameter_mm": P["stationary"]["tower_od"] + 2 * P["stationary"]["labyrinth_radial_gap"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "outer_diameter", "type": "cylinder", "diameter_mm": P["lower_hub"]["od"], "diameter_tolerance_mm": tol, "count": 1}]},
        "bearing_support_stationary": {"expect_solids": 1, "features": [
            {"name": "bearing_seats", "type": "cylinder", "diameter_mm": P["bearings"]["seat_bore_diameter"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "mid_bore", "type": "cylinder", "diameter_mm": 11.0, "diameter_tolerance_mm": tol, "count": 1},
            {"name": "tower_od", "type": "cylinder", "diameter_mm": P["stationary"]["tower_od"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "throat", "type": "cylinder", "diameter_mm": P["stationary"]["throat_id"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "m3_pilot_90deg", "type": "cylinder", "diameter_mm": 2.6, "diameter_tolerance_mm": tol, "count": 1, "axis": "+y"},
            {"name": "m3_pilot_210deg", "type": "cylinder", "diameter_mm": 2.6, "diameter_tolerance_mm": tol, "count": 1, "axis": "other"},
            {"name": "m3_pilot_330deg", "type": "cylinder", "diameter_mm": 2.6, "diameter_tolerance_mm": tol, "count": 1, "axis": "other"}]},
        "roof_flash_adapter": {"expect_solids": 1, "features": [
            {"name": "throat", "type": "cylinder", "diameter_mm": P["stationary"]["throat_id"], "diameter_tolerance_mm": tol, "count": 1},
            {"name": "roof_screw_holes", "type": "cylinder", "diameter_mm": P["stationary"]["flange_screw_hole"], "diameter_tolerance_mm": tol,
             "count": P["stationary"]["flange_screw_count"]},
            # 3 radial holes at 90/210/330 deg: agentcad buckets cylinders by axis (+y, and two 'other')
            {"name": "support_screw_clearance_90deg", "type": "cylinder", "diameter_mm": 3.4, "diameter_tolerance_mm": tol, "count": 1, "axis": "+y"},
            {"name": "support_screw_clearance_210deg", "type": "cylinder", "diameter_mm": 3.4, "diameter_tolerance_mm": tol, "count": 1, "axis": "other"},
            {"name": "support_screw_clearance_330deg", "type": "cylinder", "diameter_mm": 3.4, "diameter_tolerance_mm": tol, "count": 1, "axis": "other"}]},
    }
    res = {"inspect": {}, "check_spec": {}}
    for f in sorted(STEP.glob("*.step")):
        d = run(["inspect", str(f), "--summary"])
        v = d.get("validation", {}) if isinstance(d, dict) else {}
        res["inspect"][f.name] = {"status": d.get("status"), "is_valid": v.get("is_valid", d.get("is_valid")),
                                  "first_failure": v.get("first_failure")}
    for name, spec in specs.items():
        p = SPEC / f"{name}.spec.json"
        p.write_text(json.dumps(spec, indent=2))
        d = run(["check-spec", str(STEP / f"{name}.step"), str(p)])
        res["check_spec"][name] = {"passed": d.get("passed"),
                                   "missing": [m.get("name") for m in d.get("missing_features", [])],
                                   "matched": [(m["name"], m["measured"]["diameter_mm"], m["measured"]["count"]) for m in d.get("matched_features", [])],
                                   "failed_rows": [m["name"] for m in d.get("matched_features", []) if not m.get("passed")]}
    # STEP round trip: reload the assembly and compare solid count and volumes with the live model
    from build123d import import_step
    import assembly as A
    items = A.build(P, D)
    sol = import_step(str(STEP / "whirlybird_complete_assembly.step")).solids()
    cad = sorted(it.shape.volume for it in items)
    stp = sorted(s.volume for s in sol)
    res["step_round_trip"] = {"solids_model": len(cad), "solids_step": len(stp),
                              "volumes_match": len(cad) == len(stp) and all(abs(a - b) <= max(0.05, 1e-5 * a) for a, b in zip(cad, stp))}
    res["all_valid"] = all(v["is_valid"] for v in res["inspect"].values()) and res["step_round_trip"]["volumes_match"]
    res["all_specs_pass"] = all(v["passed"] for v in res["check_spec"].values())
    (REP / "agentcad_validation.json").write_text(json.dumps(res, indent=2))
    for k, v in res["inspect"].items():
        print(f"{'ok ' if v['is_valid'] else 'BAD'} {k} {v['first_failure'] or ''}")
    for k, v in res["check_spec"].items():
        print(f"spec {k}: passed={v['passed']} missing={v['missing']} failed={v['failed_rows']}")
    print("STEP round trip", res["step_round_trip"])
    print("ALL VALID", res["all_valid"], "ALL SPECS", res["all_specs_pass"])
    return 0 if res["all_valid"] and res["all_specs_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
