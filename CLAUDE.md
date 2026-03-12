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

## Blender MCP (Multi-Port Setup)

- Up to 4 worktrees can connect to Blender simultaneously on ports **9876–9879**
- Port selection is automatic — `.mcp.json` runs `blender_mcp_pick_port.py` (in `~/.local/bin/`)
- The script uses `netstat` to detect occupied ports and picks the first free one
- The Blender addon (`blender_mcp_addon.py`) rejects second connections to the same instance
- **Blender side**: each instance must have a unique port set in N-panel > BlenderMCP, with "Connect to MCP server" clicked
- **No manual config needed per worktree** — just restart the session and it auto-connects
- **Check your port**: `cat .blender_port` to see which Blender instance you're connected to
