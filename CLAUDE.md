# Project Rules

## Directory Structure

- `scripts/` — Production pipeline scripts only (vrm_to_mixamo_fbx, test_spring_bones, build_training_pairs, package_dataset, check_animation_range)
- `tests/` — All test/debug scripts (test renders, VRM debug, camera angle tests, etc.)
- `archive/` — Deprecated scripts and data from abandoned approaches (gitignored)
- `data/renders/` — Final sprite sheets and GIFs only (no test images)

## Test & Debug Output Policy

- All test renders, debug images, and temporary output MUST go into `tests/output/` (gitignored)
- Never write test/debug images to `data/renders/` or the project root
- Test scripts belong in `tests/`, not `scripts/`
- Name test scripts with `test_` or `debug_` prefix

## Rendering

- Final sprite sheets go to `data/renders/sheet_XX_name.png` and `.gif`
- Per-frame render subdirs go to `data/renders/sheet_XX/` (gitignored)
