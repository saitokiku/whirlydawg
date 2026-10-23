# Doghouse whirlybird – design report (DW-V1.1)

All numbers below come from the parametric CAD (`cad/`), driven by `MASTER_PARAMETERS.json`.
Nothing in this package is a concept image: every render, section and drawing is a projection of
the build123d solids that are also exported as STEP/STL.

## 1. What was built

| Item | Result |
|---|---|
| Configuration | 8 identical vertical aluminium vanes between two printed caps on a rotating 1/4 in shaft; stationary 2-bearing tower in a roof flash adapter |
| Installed height (roof surface at axis → rotor top) | **165.2 mm (6.51 in)**, 25.3 mm under the 190.5 mm limit (flat roof) |
| Rotor OD incl. bowed blades | **259.1 mm (10.20 in)**; 245.4 mm at the cap faces |
| Hub OD (upper / lower) | 188 / 188 mm (single prints, fit the X1E bed) |
| Blade | 57.15 × 139.7 mm blank, 1.6 mm Al, 14 × 7 mm tabs offset 4 mm from the inner edge, R2 roots, 15 mm vertical bow |
| Plan chord angle | 35° from radial, same hand on every blade |
| Cap separation (blade shoulders) | 121.24 mm (set at assembly by seating the upper hub on the shoulders) |
| Blade-to-blade clearance | 50.5 mm minimum (bow included) |
| Rotor-to-stationary clearance | 6.0 mm axial (hub face to collar/support ring), 2.0 mm radial labyrinth (rotating cup over stationary tower) |
| Bearings | 2 × R4-2RS, 50 mm apart, outer races in the stationary tower only |
| Shaft | 6.35 mm × 201.8 mm (your 209.55 mm tube is long enough *if* it slips into the bearings) |
| Throat | 127 mm (5 in hole saw) |
| Blade-to-hub hardware | **none**. Hub-to-shaft: 2 × M4 set screws in drilled shaft dimples |

## 2. Requirement conflicts found and how they were resolved (please review)

1. **"Lower hub completely closed bottom" vs "lower opening substantially unobstructed".**
   A solid 188 mm disc 6 mm above a 127 mm throat leaves only π × 127 × 6 ≈ 2 390 mm² of escape area,
   about **19 %** of the throat (12 670 mm²). The rotor would barely ventilate.
   **Resolution:** the lower hub is a closed-bottom *pocket ring* (every pocket blind with a 3.5 mm
   intact floor, nothing passes through the underside or the OD), joined by 4 slender spokes to the
   shaft boss, with a 25 mm *chimney* (ID 127) rising from the ring. Exhaust air goes up through the
   open centre and out between the blades, as in a traditional whirlybird. The fully solid version is
   exported as `lower_hub_SOLID_DISC_ALTERNATE_not_recommended.*` in case you prefer it anyway.
2. **267 mm rotor OD with 150/160 mm hubs.** With a centred tab on a 150 mm hub the rotor reaches only
   about 200 mm. **Resolution:** hubs grown to 188 mm. The spec range for the top cap is ~135–185 mm, so
   that is 3 mm over. The extra 3 mm is needed to keep at least 3 mm of wall outside the chamfered
   pocket mouth. Tabs are offset toward the blade's inner edge so the body overhangs outward.
   **Reported OD: 259.1 mm** (inside the 254–279 mm window, 7.6 mm below target). If you want 267 mm:
   a 20 mm bow gives 264 mm, and a 63.5 mm chord gives ~270 mm. Both cost formability or stock (see
   `reports/variant_study.csv`).
3. **Crowned top vs printability.** A crowned 188 mm top would need full supports under a dome. The
   upper hub is printed **top face down**, so the 8 blind pockets print as open, accurate slots with no
   support. The top is therefore flat with a 2 mm chamfer and a notched 2.5 × 4 mm drip lip. Rain
   leaves by rotation, wind and the lip.
4. **"Curved" blades with stock that can only be bent along its length.** The blades are straight in
   plan and bowed vertically: d(z) = s·sin²(πz/H). Zero slope at both shoulders keeps both tabs
   straight, vertical and coaxial. A uniform springback only scales the bow, so the tabs stay aligned.
   It is formed in one squeeze with the printed die.
5. **Positive retention without per-blade hardware.** Each blade is trapped by (a) its shoulders
   seated on both hub faces, (b) the closed ends and sides of each blind pocket, and (c) both hubs
   fixed to the shaft by set screws sitting in drilled dimples. That makes the fixing positive, not
   friction-only. CAD check: lifting a seated blade 0.6 mm or pushing it 1 mm outward collides with a
   hub, so it cannot escape.
6. **Rain.** Plan coverage of the 8 blades is 58 % of each 45° sector, so there is **no shingled
   overlap** and line-of-sight gaps exist. Protection comes from the 188 mm closed cap overhang, the
   25 mm chimney, the drip lip and the weeps. An optional stationary drip tray goes under the throat.
   **It is not waterproof.** Gate F (spray test) decides whether the tray is needed.
7. **Roof pitch unknown.** CAD is built for 0°. Adapters for 0, 2/12, 3/12, 4/12 and 5/12 are
   exported. The rotor must lift to clear the uphill roof: 4/12 gives 185.4 mm (OK), 5/12 gives
   191.0 mm, which **exceeds 190.5 mm**. On a steeper roof, mount at the ridge, or shorten the blades.
8. **Bambu project file.** A Bambu Studio-saved 3MF cannot be produced in this environment (no Bambu
   Studio), and the spec forbids passing off generic 3MF as Bambu-compatible. The STLs are delivered
   **already in print orientation**. Import them, set the filament, save the project (see
   PRINT_AND_ASSEMBLE.md).

## 3. Mechanical checks (sheet 12 of `fabrication_drawings.pdf`)

| Check | Value | Note |
|---|---|---|
| Blade mass | 31.9 g (set of 8 = 255 g) | 1.6 mm Al, ρ 2.70 |
| Centrifugal load @ 1000 rpm (design check, not expected rpm) | 35.4 N/blade, 17.7 N/tab | CG radius 101 mm |
| Tab bearing stress @ 1000 rpm | 1.6 MPa | 1.6 × 7 mm contact |
| Proof pull target | 50 N per tab | 2.8× the 1000 rpm load: keep 50 N |
| Pocket end-wall shear-out | > 1 kN (estimate) | ≥ 3.5 mm wall × 8.5 mm deep, 2 shear planes |
| Thermal (Al blades vs SS shaft, ΔT 60 K) | 0.04 mm separation change | engagement 7 mm |
| Wind uplift on upper cap (25 m/s) | ~5–10 N | carried by set screw in dimple |
| Hub hoop stress @ 1000 rpm | < 0.1 MPa | negligible |

## 4. Automated design gates (all PASS, `reports/design_checks.json`)

No unintended solid interference. Rotor and stator never touch. 6 mm axial gap. Blade-to-blade and
blade-to-stationary clearance. Tab clearance in the pocket and no bottoming out. Upper top face is a
single closed plane. Pocket walls ≥ 3 mm to every exterior face. Hex-key access to both set screws
through blade gaps. Assembly sequence collision-free: each blade dropped 12 mm into the lower hub,
then the upper hub dropped 14 mm over all 8 tabs. Blades trapped once hubs are fixed. Height
≤ 190.5 mm. CAD top equals reported height. Roof clearance ≥ 6 mm. Every printed part fits the X1E
bed. Shaft fits the tube length. All STLs watertight, manifold, single body, volume within 1 %.

Independent checks: `agentcad inspect` reports all 25 STEP files valid (kernel, closed shells,
manifold mesh). `agentcad check-spec` passes for the hubs, bearing support and adapter (bores, seats,
holes). The assembly STEP round-trips with 27/27 solids and matching volumes.

## 5. Assumptions (all editable in MASTER_PARAMETERS.json)

* Roof pitch 0° and deck 15 mm (unknown).
* Pocket width 1.95 mm, hub bore 6.55 mm and bearing seat 15.95 mm are **placeholders until the
  coupons are tested**.
* R4 bearing: 6.35 × 15.875 × 4.92 mm, inner-race land Ø8.6 mm. The thrust washers must touch the
  inner race only. Measure your bearing's inner ring OD and adjust `inner_race_land_od`.
* Aluminium alloy and temper unknown; die springback factor 1.30 is a first guess.
* M4 set screws with DIN 934 nuts; 1/4 in set-screw shaft collar (OD 12.7, width 7.9).
* Filament: PAHT-CF recommended for the final hubs (heat, UV-stable carbon fill, stiffness);
  PETG-HF for fit trials.

## 6. Still requires physical validation

1. Coupons (gate B): pocket width, bearing seat, shaft bore.
2. One blade (gate C): cut, form, measure bow and shoulder spacing; adjust springback factor.
3. Bearing ID versus your tube and rod (do not force).
4. Assembly, retention and 50 N pull test (gate D), and free spin plus balance (gate E).
5. Spray and airflow test against a plain vent (gate F). Rpm, CFM and rain ingress are **not
   predicted** by this CAD.
6. Roof pitch and deck: measure, set `roof_pitch_deg`, rebuild, and use the matching adapter.
