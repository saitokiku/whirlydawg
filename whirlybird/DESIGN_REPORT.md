# Doghouse whirlybird – design report (DW-V2.0)

All numbers come from the parametric CAD (`cad/`), driven by `MASTER_PARAMETERS.json`.
Every render, section and drawing is a projection of the build123d solids that are also exported
as STEP and STL.

## 0. What changed from V1 (and why)

V1 had 8 flat vanes, bowed vertically, with 50 mm open gaps between them. That doesn't work like a
real whirlybird:
- **Too open:** about 58 % of the ring was covered, so wind blew straight through.
- **No scoop:** the vanes had no cupped face for the wind to push on, so they produced little
  turning force.

V2 is laid out like a commercial turbine vent:

| | V1 (open) | **V2 (closed, cupped)** |
|---|---|---|
| Blades | 8 × 57 mm, bowed vertically | **20 × 44.5 mm, cupped across the width (R45, 5.4 mm deep)** |
| Angle from radial | 35° | **55°** |
| Plan coverage of the ring | 58 % (open gaps) | **100.3 % (closed: no straight line of sight)** |
| Air channel between blades | 50 mm | **11.5 mm** (narrow, angled channels) |
| Cap OD | 188 mm | **248 mm** (covers the vane ring) |
| Rotor OD | 259 mm | **257.9 mm** |
| Installed height | 165.2 mm | **169.7 mm** (limit 190.5) |
| Upper hub held by | set screw (unreachable once the ring is closed) | **M4 tie rod through the hollow shaft**, tightened from below |
| Stock needed | 4 pieces | **5 pieces** (4 blanks per piece) |

The cup is a single bend across the width, made over a cylinder. It's still a simple-curvature
part: no compound forming and no twist. The blade stays straight along its length, so both tabs
are in line. The tabs are curved like the blade, and the hub pockets are curved to match.

## 1. Key results

| Item | Result |
|---|---|
| Installed height (roof surface at axis → rotor top) | **169.7 mm (6.68 in)**, 20.8 mm under 190.5 |
| Rotor OD | **257.9 mm (10.15 in)**: blade tips; caps 248 mm |
| Blade ring | r 104.5 → 129.0 mm; 20 vanes every 18° |
| Plan coverage / air channel | 100.3 % / 11.5 mm minimum between neighbouring blades |
| Blade | 44.5 × 139.7 mm blank, 1.6 mm Al, centred 14 × 7 mm tabs, R2 roots; 25.0 g each, 500 g set |
| Cap separation | 125.7 mm (= blade body length) |
| Rotor ↔ stationary | 6.0 mm axial, 2.0 mm radial labyrinth |
| Bearings | 2 × R4-2RS, 50 mm apart, outer races in the stationary tower only |
| Shaft | 1/4 in × 0.035 in wall stainless **tube**, 198.8 mm (your 209.55 mm tube is long enough) |
| Upper-hub retention | M4 rod (211 mm) in the tube → captive M4 nut in the hub; washer + nyloc under the tube |
| Lower-hub retention | M4 set screw into a drilled shaft dimple (tightened before the blades go in) |
| Blade hardware | **none**: tabs trapped in blind pockets |

## 2. Requirement conflicts and decisions (please review)

1. **Closed ring vs. stock and mass.** The overlapping ring needs 20 blades. Narrowing them to
   44.5 mm lets 4 blanks come from each 11.75 × 3.75 in piece, so you need 5 pieces (V1 needed 4).
   The blade set weighs 500 g: heavier than a sheet-metal whirlybird, because your stock is 1.6 mm.
   That affects how fast it spins up, not how fast it can turn.
2. **Lower hub "completely closed bottom" vs. an unobstructed exhaust.** Unchanged from V1:
   - The pocket ring is closed under every pocket.
   - The centre is open through a 127 mm chimney, so air can leave.
   - A solid-disc alternate is exported but not recommended (it would leave about 19 % of the
     throat's flow area).
3. **Caps are 248 mm, over the spec's 135–195 mm range.** The caps have to cover the vane ring (as
   on a real whirlybird) and leave at least 3 mm of wall outside each pocket (5.6 mm achieved). 248 mm
   is the largest that fits the X1E bed with its 3 mm margin.
4. **Flat top** (with chamfer and notched drip lip), so the caps print without supports in the
   pockets. Same reasoning as V1.
5. **Upper-hub fixing changed.** With the ring closed, no hex key can reach a set screw inside the
   rotor. A tie rod through the hollow shaft keeps the top closed and is tightened from below the
   bearing tower. It also puts the blades under light compression, so they don't rattle.
6. **Rain.** The closed, overlapping ring plus the 248 mm cap covering it give much better shading
   than V1. It is still **not waterproof** in severe wind-driven rain; the optional drip tray remains.
7. **Roof pitch unknown.** Adapters for 0 to 5/12 are exported. The 248 mm caps must lift to
   clear an uphill roof:
   - 0/12: 169.7 mm
   - 2/12: 178.8 mm
   - 3/12: 186.7 mm (OK)
   - 4/12: 197.0 mm (over the 190.5 mm limit)
   - 5/12: 207.4 mm (over the limit)

   On a roof steeper than 3/12, mount at the ridge or accept the extra height.
8. **Bambu project file** not generated (no Bambu Studio here). The STLs are pre-oriented: import
   them and save the project.

## 3. Mechanical checks

| Check | Value | Note |
|---|---|---|
| Blade mass | 25.0 g (set of 20 = 500 g) | 1.6 mm Al |
| Centrifugal load @ 1000 rpm (design check) | 31.0 N/blade, 15.5 N/tab | CG radius 113 mm |
| Tab bearing stress @ 1000 rpm | 1.4 MPa | |
| Proof pull target | 50 N per tab | 3.2× the 1000 rpm load: keep 50 N |
| Pocket end-wall shear-out | > 1 kN (estimate) | ≥ 3.5 mm wall × 8.5 mm deep |
| Cup forming | die radius 33.3 mm for R45 at springback 1.35 | R/t ≈ 28, easy for aluminium |
| Tie-rod preload | light: snug until the shoulders seat, then 1/4 turn | blades act as compression struts |

## 4. Automated design gates (all PASS: `reports/design_checks.json`)

| Area | What is checked |
|---|---|
| Interference | No solid interference anywhere in the assembly |
| Rotor vs. stationary | Never touch; 6 mm axial gap to the collar and support |
| Blade spacing | Blade-to-blade air channel ≥ 10 mm (11.5 mm) |
| Closed ring | Plan coverage ≥ 100 % (100.3 %) |
| Clearance | Blade to every stationary part |
| Tabs | Clearance in the pocket, and they don't bottom out |
| Blind pockets | Upper top face is one closed plane; ≥ 3 mm wall to every exterior face |
| Fixings | Reachable with the ring closed |
| Assembly sequence | Collision-free: each blade drops into the lower hub, the upper hub drops over 20 tabs |
| Retention | Blades trapped (axial and radial) once the hubs are fixed |
| Height | ≤ 190.5 mm, and the CAD top matches the reported height |
| Roof | Clearance ≥ 6 mm |
| Printing | Every printed part fits the X1E bed |
| Shaft | Fits your tube's length |
| Meshes | All STLs watertight, single body, volume within 1 % |

Independent checks:
- **`agentcad inspect`:** every STEP file valid.
- **`agentcad check-spec`:** passes for the hubs, support and adapter.
- **Assembly STEP round trip:** 41 / 41 solids, all volumes match.

## 5. Assumptions (editable in MASTER_PARAMETERS.json)

* **Roof:** pitch 0° and deck 15 mm (both unknown).
* **Placeholders until you print the test pieces:**
  - pocket width 1.95 mm
  - hub bore 6.55 mm
  - bearing seat 15.95 mm
* **Springback:** the cup die factor of 1.35 is a first guess (alloy and temper unknown).
* **Shaft:** your tube's ID of 4.54 mm (measured) passes an M4 rod. The tube must also slip into
  both bearings without force; this is unverified.
* **Spin direction:** set by the cup hand and not predicted. Rpm, airflow and rain ingress must be
  measured (gates E and F).

## 6. Still requires physical validation

1. Test prints: pocket width, bearing seat, shaft bore.
2. One blade: cut, roll the cup, check it on the 1:1 cup gauge, adjust the springback factor.
3. Tube vs. bearings; M4 rod through the tube.
4. Assembly, retention, 50 N pull test; free spin and balance.
5. Spray and airflow test against a plain vent.
6. Roof pitch: measure it and use the matching adapter.
