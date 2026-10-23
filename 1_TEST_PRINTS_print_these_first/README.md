# Step 1 – print these test pieces first

They are small and quick, and they tell you the sizes that fit **your** aluminium, bearings and
shaft before you spend hours printing the big parts. Print them in the same filament you'll use
for the final caps.

| File | Test |
|---|---|
| `slot_clearance_coupon_1p85_1p95_2p05_2p15.stl` | 4 slots of different widths. Pick the narrowest one a 1.6 mm aluminium strip slides into by hand without wobbling. |
| `single_blade_socket_test_top.stl` | one slot exactly as it is in the top cap (opens from one side only) |
| `single_blade_socket_test_bottom.stl` | one slot exactly as it is in the bottom cap, with its tiny drain hole |
| `bearing_and_shaft_fit_coupon.stl` | 4 bearing holes and 3 shaft holes. Pick the bearing hole it presses into firmly, and the shaft hole it slides through without wobble. |

Write down the sizes that worked. If they differ from the defaults (1.95 slot, 15.95 bearing,
6.55 shaft), update `whirlybird/MASTER_PARAMETERS.json` and rebuild before printing folder 3.
Full pass/fail checks: `PRINT_AND_ASSEMBLE.md`, Phase 0.
