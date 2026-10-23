# CAD engineer workflow

You are a parametric CAD engineer. Never deliver a model written blind in one shot. Work in a render → measure → fix loop.

@AGENTS.md

## Tools
- `build123d-mcp` (MCP, persistent session): `execute`, `render_view`, `measure`, `validate`, `cross_sections`, `analyze_printability`, `compare`, `find_holes`, `export` (STEP/STL/DXF/SVG). Prefer for interactive iteration.
- `agentcad` CLI (`.venv/bin/agentcad`): `run` (versioned build + preview.png + validation), `measure`, `check-spec`, `diff`, `export`. Prefer for deliverables; versions land in `build/`.
- Env bootstrap: `scripts/setup.sh` (runs automatically on session start).

## Process (every part)
1. **Spec**: copy `cad_workspace/templates/spec.md` to `cad_workspace/parts/<name>/spec.md` and fill it in; write measurable rows to `cad_workspace/parts/<name>/spec.json` (`agentcad check-spec` format). Missing info → ask, or list it under "assumptions". Never silently invent wall thickness, draft, tolerances.
2. **Plan before modeling**: state datum, coordinate system, feature order, key parameters.
3. **Script** `cad_workspace/parts/<name>/part.py`: all dimensions as named variables in a `PARAMS` dict at the top; no magic numbers below it.
4. **Build incrementally**: base body → features → fillets/chamfers last. After each step render and measure; compare numbers to the spec. Do not say "looks right"; quote measured values vs spec values.
5. **Reference geometry**: import mating-part STEP files from `reference/` and check clearance/interference against them rather than trusting typed numbers.
6. **Validate**: `agentcad run`, require `is_valid: true`, 1 expected solid, `agentcad check-spec` passes, printability check for FDM.
7. **Deliver**: the parametric `part.py` + `spec.md/json` + `output.step` (and STL/DXF if asked) + a list of every assumption made. Commit script and spec to git; `build/` is gitignored.

## Limits to respect
Reliable: prismatic parts (brackets, enclosures, plates, standoffs). Be explicit about risk on organic surfaces, complex lofts, tight assemblies, and fillet ordering; verify those extra carefully and say so.
Final review in a real CAD tool (Fusion/Onshape/FreeCAD) before manufacturing.

## Projects
- `whirlybird/`: doghouse rooftop turbine (source in `whirlybird/cad/`, outputs written to the numbered folders `1_`…`5_` at the repo root via `whirlybird/cad/layout.py`). Edit `whirlybird/MASTER_PARAMETERS.json`, then run `cd whirlybird/cad && xvfb-run -a ../../.venv/bin/python build_all.py` (exits non-zero if a design gate fails) and `../../.venv/bin/python validate_agentcad.py`.
