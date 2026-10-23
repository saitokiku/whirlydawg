# Print and assemble – doghouse whirlybird (DW-V1.1)

Work through the phases in order. Each phase ends with a check; do not skip ahead.
File paths are relative to `whirlybird/deliverables/`.

## Phase 0 – Print the fit coupons first (≈1–2 h, ~70 g)

Print in **the same filament you will use for the final hubs** (fit depends on material).

| File (`stl/`) | What it tells you |
|---|---|
| `slot_clearance_coupon_1p85_1p95_2p05_2p15.stl` | best pocket width for your 1.6 mm aluminium |
| `single_blade_socket_test_top.stl` / `_bottom.stl` | one real pocket from each hub incl. lead-in, blind roof/floor, weep |
| `bearing_and_shaft_fit_coupon.stl` | bearing seat (15.80 / 15.90 / 16.00 / 16.10) and shaft bore (6.45 / 6.55 / 6.65) |

**Pass (gate B):**
- **Tab:** an offcut tab (14 mm wide, 1.6 mm) slides in by hand and rocks less than about 0.3 mm at the tip.
- **Plastic:** no whitening or layer splitting when you wiggle the tab, and the tab cannot be pushed through any outer face.
- **Bearing seat:** the bearing goes in with firm thumb pressure and does not rattle.
- **Shaft bore:** the rod slides with light force and does not wobble.

Then edit `MASTER_PARAMETERS.json`:
- `pocket.width`
- `bearings.seat_bore_diameter`
- `shaft.hub_bore_diameter`

Regenerate with `cd cad && xvfb-run -a python build_all.py` (or ask Claude to do it).

## Phase 1 – One blade only (gate C)

1. **Print the template.** Print `pdf/blade_and_roof_templates_1to1.pdf` page 1 at **100 % / actual size**. Check the 50 mm and 2.000 in bars with calipers.
2. **Cut the blank.** Glue the template to the stock. Rip to 57.15 mm, then crosscut to 139.7 mm, cutting on the waste side of the line.
3. **Notch the tabs.** Saw or snip to 2 mm short of the shoulder, then file the R2 roots. Break all edges, round the outer corners R2, and chamfer the tab tips 1 × 45°. **Do not drill any holes.**
4. **Print the die.** Print `blade_forming_die_lower.stl` and `blade_forming_die_upper.stl`: PETG-HF or PLA, 6 walls, 50 % infill, as oriented.
5. **Form the blade.** Drop the blank into the lower die. The key blocks only let it sit tab-side correct. Squeeze the stack in a bench vise until the die faces meet, then release.
6. **Measure the blade.** Lay it on the 1:1 profile gauge (template page 1).
   - Target bow: 15 ± 1.5 mm.
   - Shoulder spacing: 121.2 ± 0.5 mm.
   - Tabs: flat, parallel and in line.
   - If it's too flat, raise `forming_die.springback_factor` (now 1.30) and reprint the upper and lower die.
7. **Test the fit.** Insert both tabs into the coupons; the blade must line up without twisting.

Then cut and form the other 7 blades using the nest in `dxf/blade_flat_pattern_8x.dxf`: 2 blades per 11.75 × 3.75 in piece, 4 pieces in total. **Install all 8 the same way:** tab at the shaft-side edge, bow bulging outward.

## Phase 2 – Print the parts

The STL files are **already in print orientation**. In Bambu Studio, import them all (*File → Import*), do **not** auto-orient, assign filament per plate, and *Save Project* (that is your Bambu-native 3MF). No G-code is provided.

| Part (`stl/`) | Filament (final) | Orientation (as exported) | Walls / top-bottom / infill | Supports | Notes |
|---|---|---|---|---|---|
| `upper_hub_closed_top` | PAHT-CF (or PETG-HF) | closed top **down** | 5 / 6 / 40 % gyroid | none | pockets print as open slots: no support in pockets |
| `lower_hub_closed_bottom` | PAHT-CF (or PETG-HF) | closed bottom **down** | 5 / 6 / 40 % gyroid | none (28 mm cup ceiling bridges) | 4–5 mm brim on PAHT-CF |
| `bearing_support_stationary` | PAHT-CF or ABS | tower top **down** | 5 / 6 / 50 % | **tree, build-plate only**, under ring + spokes (12 mm) | supports never touch bearing seats |
| `roof_flash_adapter_pitch_XinY` (pick yours) | ABS (paint it) or PAHT-CF | roof face down | 4 / 5 / 30 % | none | gasket groove bridges 4 mm |
| `thrust_washer_top` / `_bottom` | PETG-HF | flat | 100 % | none | print 2 of each (spares) |
| `rain_baffle_if_needed` | PETG-HF | floor down | 3 / 4 / 20 % | none | only if gate F shows water |
| `inlet_vent_louver` ×2 | PETG-HF / ABS | plate down | 3 / 4 / 20 % | none | 45° louvres self-support |
| `shaft_dimple_drill_guide` | PETG-HF | as exported | 4 / 5 / 50 % | none | ream bore with 1/4 in drill if tight |

**Profile:** 0.20 mm layers, 0.4 mm nozzle.

**Filament notes:**
- **PAHT-CF:** dry before printing (about 80 °C for 8–12 h). Use a hardened nozzle (the X1E ships with one), a textured PEI plate with glue, and a closed, warm chamber.
- **PETG-HF:** fine for trials and for outdoor use if the roof doesn't stay hot. Its manufacturer heat-deflection temperature is about 69 °C, and a dark top in Texas sun can exceed that.
- **ABS and PC-FR:** these are not UV-stable. Paint them with exterior acrylic.
- **PLA:** don't use it on the roof.

Bambu Studio reports the real time and filament weight. The CAD-volume estimate at ~55 % effective fill (PETG) is about 165 g per hub, 29 g for the support and 90 g for the adapter.

## Phase 3 – Hardware

See `BOM.csv`. You need:
- **Shaft:** a 1/4 in stainless rod cut to **201.8 mm**, or your 209.55 mm tube trimmed to length if it slips into both bearing inner races *without force*.
- **Hub fixings:** 2 × M4 × 6 cup-point set screws and 2 × M4 nuts.
- **Shaft collar:** one 1/4 in bore set-screw collar.
- **Support screws:** 3 × M3 × 12.
- **Roof screws:** 8 × #8 × 3/4 in stainless pan-head screws with EPDM washers.
- **Sealant:** butyl or polyurethane.
- **Screen:** fibreglass or aluminium for the inlet louvres.

## Phase 4 – Assemble (order proved collision-free in CAD)

1. **Bearings.** Press one R4-2RS into the top seat of the support tower (from above) and one into the bottom seat (from below), outer races only. Use a socket that bears on the outer race.
2. **Shaft.** Thread the bottom thrust washer and the shaft collar loosely onto the shaft. Push the shaft **up** through both bearings from below. It must turn freely.
3. **Top washer.** Drop the top thrust washer onto the shaft so it rests on the upper bearing inner race. It must not touch the outer race or seal.
4. **Lower hub.** Slide it down the shaft until its cup ceiling sits on that washer.
   - Drop an M4 nut into the nut slot, thread the set screw in, and snug it to mark the shaft.
   - Remove the shaft and spot-drill a 3.5 mm × ~1 mm dimple at the mark, using `shaft_dimple_drill_guide` clamped in a vise.
   - Refit, then tighten with medium threadlocker.
   - Slide the collar up under the bottom washer leaving **0.2 mm end play** (a paper shim) and tighten its screw.
5. **Blades.** Lower each blade **straight down** into a lower-hub pocket. All 8 the same way: tab toward the shaft, bow outward.
6. **Upper hub.** Lower it **straight down** over all 8 upper tabs; the 2 mm lead-ins guide them. Press lightly (about 20 N) until every shoulder seats. Don't load it up: the bowed blades are springs.
7. **Lock the upper hub.** Mark through the upper set-screw hole, take the upper hub off (the blades stay in the lower hub), dimple the shaft, refit, and tighten with threadlocker. The blades are now trapped, with no per-blade hardware.
8. **Check.**
   - **Spin and pull (gate D/E):** spin by hand. There should be no rub, no rattle, and no blade touching anything stationary. Pull test each blade at about 50 N (a luggage scale) in the radial and axial directions; it must not move.
   - **Balance:** stand the cartridge on its tower, let the rotor settle, and put tape weights on the light side of the upper hub rim until it stops anywhere.

## Phase 5 – Roof installation

1. **Cut the hole.** Mark the centre and cut a **127 mm (5 in)** hole (template page 3 also shows the 8 screw holes). Seal the plywood edge with exterior paint.
2. **Fit the adapter.** Use the adapter for your pitch. A pitched adapter only sits flat one way: the collar is taller on the downhill side. Run a continuous sealant bead in the underside groove. On shingles, slip the uphill half of the flange under the course above. Drive the 8 screws and seal the heads.
3. **Drop in the rotor.** Lower the rotor cartridge (support ring and bearings) into the collar counterbore until it sits on the step, then drive 3 × M3 screws through the collar into the support bosses.
4. **Inlets.** The turbine cannot exhaust a sealed box. Cut 2 × 140 × 90 mm openings low on opposite gable or end walls (away from prevailing rain). Fit `inlet_vent_louver` from outside with screen in the recess behind, and keep them out of the dog's reach and chewing range.
5. **Spray test (gate F).** On a mock roof, not over the dog, spray water across the rotor and catch anything that comes through the throat. Fit `rain_baffle_if_needed` on the tower bottom (1 M3 clamp screw) if water collects. Press a 1/4 in OD vinyl tube into its drain hole and route it outside, or plug it.
6. **Airflow comparison.** Compare against a plain 127 mm vent with an anemometer in light wind before you call it better.

## Drainage and maintenance

- **Weeps:** each lower pocket drains through a concealed 1.6 mm diamond weep to the hub OD. Twice a year, clear the weeps with a 1.5 mm wire.
- **Water on the lower ring:** it runs off the edge. Nothing drains into the bearings: the rotating cup over the stationary tower is a 2 mm labyrinth, and both bearings are 2RS sealed. A dab of grease where the shaft enters the lower boss stops water wicking down the shaft.
- **Service:** remove the 3 M3 screws and the whole rotor and bearing cartridge lifts out. Bearings are standard R4-2RS.
- **Inspect yearly:** pockets for cracks, set screws for tightness, blades for fatigue at the tab roots.

## Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| Tab too tight or splits the pocket | width too small → next coupon size up, rebuild |
| Blade rattles | width too large → next size down; or upper hub not seated |
| Upper hub won't drop over the tabs | tabs not vertical or in line → re-press the blade in the die; check the tabs are flat |
| Blades differ in height by more than 0.5 mm | blank length or bow varies → re-cut to the template; form all 8 in the same die |
| Rotor drags | washer touching the bearing seal or outer race → reduce `inner_race_land_od`; check 0.2 mm end play |
| Rotor wobbles | shaft bore oversize or set screw not in its dimple → tighter bore coupon; re-dimple |
| Rubs the collar | the 6 mm gap is set by the lower hub sitting on the top washer → check the washer is present |
| Vibration in wind | unbalanced → re-balance; stop immediately if oscillation grows (gate E) |
