# Part spec: <name>

Units: mm. Process: <FDM | CNC | sheet metal | resin>. Material: <...>. Qty: <n>.

## Datum & coordinates
- Origin: <e.g. bottom-centre of the part>   Up axis: +Z   Front face: -Y

## Parameters (single source of truth, become named variables in the script)
| name | value | tol (±) | notes |
|---|---|---|---|
| length | | | |
| width | | | |
| height | | | |
| wall | | | min for process: FDM 1.2, CNC 1.0 |
| hole_d | | | clearance vs tapped? |

## Features (in build order: base body, features, fillets last)
1. Base body:
2. Holes / pockets:
3. Fillets & chamfers (radius, which edges):

## Mating parts / reference geometry
- <PCB/connector/rail> → STEP file at `reference/<file>.step`; required clearance <x> mm

## Acceptance checks (machine-checkable)
- bbox = L x W x H ± tol
- volume ≈ <x> (if known)
- holes: <d> x <count> (goes into spec.json for `agentcad check-spec`)
- 1 solid, valid

## Explicitly NOT specified (Claude must list its assumptions here)
-
