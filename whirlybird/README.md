# whirlybird/ – design source (for editing the design)

Most people don't need this folder: the ready-to-use files are in the numbered folders at the
repo root (see the main `README.md`).

| Path | Contents |
|---|---|
| `MASTER_PARAMETERS.json` | every editable size (`inputs`), every calculated size (`derived`), open questions (`unresolved`) |
| `DESIGN_REPORT.md` | design decisions, requirement conflicts, calculations, assumptions, what still needs physical testing |
| `cad/` | Python (build123d) source that builds every part, checks it and writes all outputs |
| `reports/` | automatic check results: design gates, STL mesh checks, agentcad STEP validation, variant study |

## Rebuild
```bash
cd whirlybird/cad
xvfb-run -a python build_all.py     # all parts, 18 design checks, STEP/STL/DXF/SVG/PDF/PNG (~4 min); fails loudly if a check fails
python validate_agentcad.py         # independent STEP validation, spec checks, STEP round trip
```
Output folders are defined in `cad/layout.py`.

| Module | Role |
|---|---|
| `params.py` | loads `MASTER_PARAMETERS.json`, derives the coupled sizes (cupped-blade plan geometry, coverage and air channel, height stack, shaft and tie-rod length, roof-pitch lift) |
| `geometry.py` | every part as parametric build123d solids |
| `assembly.py` | part list, rotating/stationary role, print orientation |
| `checks.py` | interference, clearances, blind pockets, assembly sequence, bed fit |
| `flatpattern.py` | blade flat pattern, DXF and SVG |
| `views.py`, `render.py` | rendered pictures |
| `drawings.py` | PDF drawing set and 1:1 templates |
| `study.py` | 16/20/24 blade × chord angle × cup radius variant table (re-fitted to the same OD) |
