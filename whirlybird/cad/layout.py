"""Where every generated file goes. The user-facing files live in numbered folders at the
repo root (in the order you use them); source code and technical reports stay in whirlybird/."""
from pathlib import Path

WHIRLYBIRD = Path(__file__).resolve().parents[1]
REPO = WHIRLYBIRD.parent

TEST_PRINTS = REPO / "1_TEST_PRINTS_print_these_first"
BLADES = REPO / "2_BLADES_cut_and_bend"
PARTS = REPO / "3_PRINT_PARTS"
ROOF_ADAPTERS = PARTS / "roof_adapter_pick_ONE_for_your_roof_pitch"
OPTIONAL = PARTS / "optional"
DRAWINGS = REPO / "4_DRAWINGS"
IMAGES = DRAWINGS / "images"
STEP = REPO / "5_3D_MODELS_STEP"
REPORTS = WHIRLYBIRD / "reports"
BOM = REPO / "BOM.csv"

DIRS = {"step": STEP, "dxf": BLADES, "svg": BLADES, "templates": BLADES, "pdf": DRAWINGS,
        "renders": IMAGES, "reports": REPORTS}
ALL = [TEST_PRINTS, BLADES, PARTS, ROOF_ADAPTERS, OPTIONAL, DRAWINGS, IMAGES, STEP, REPORTS]


def stl_dir(name: str):
    """Folder for a printable part's STL, or None if it is not exported as STL."""
    if name.startswith(("single_blade_socket_test", "slot_clearance_coupon", "bearing_and_shaft_fit_coupon")):
        return TEST_PRINTS
    if name.startswith("blade_forming_die"):
        return BLADES
    if name.startswith("roof_flash_adapter_pitch_"):
        return ROOF_ADAPTERS
    if name == "roof_flash_adapter":
        return None          # identical to the pitch file matching roof_pitch_deg
    if name.startswith(("rain_baffle_if_needed", "lower_hub_SOLID_DISC")):
        return OPTIONAL
    return PARTS
