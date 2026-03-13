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

## Blender MCP

- Each worktree's `.mcp.json` sets `BLENDER_PORT` to connect to the correct Blender instance (ports 9871–9874). The MCP server connects at startup automatically.
- The Blender addon (`blender_mcp_addon.py`) rejects second connections to the same instance
- **Blender side**: each instance must have a unique port set in N-panel > BlenderMCP, with "Connect to MCP server" clicked
- **Check your port**: call `get_scene_info` — the `port` field in the response shows which Blender instance you're connected to
- **NEVER use `bpy.ops.wm.read_factory_settings()`** — it resets the MCP addon and kills the connection. Clear the scene manually with `bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()` instead
