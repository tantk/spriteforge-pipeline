#!/usr/bin/env bash
# Wrapper script for blender-mcp that auto-picks an available port from a pool.
# Uses lock files so multiple worktrees don't collide.

PORTS=(9876 9877 9878 9879)
LOCK_DIR="${TEMP:-/tmp}/blender_mcp_locks"
mkdir -p "$LOCK_DIR"

# Clean up lock file on exit
cleanup() {
  if [ -n "$LOCK_FILE" ] && [ -f "$LOCK_FILE" ]; then
    rm -f "$LOCK_FILE"
  fi
}
trap cleanup EXIT INT TERM

# Pick the first port whose lock file we can acquire
LOCK_FILE=""
CHOSEN_PORT=""
for port in "${PORTS[@]}"; do
  lf="$LOCK_DIR/port_${port}.lock"
  # Try to create lock file atomically (noclobber)
  if (set -o noclobber; echo $$ > "$lf") 2>/dev/null; then
    LOCK_FILE="$lf"
    CHOSEN_PORT="$port"
    break
  fi
  # Check if the process that holds the lock is still alive
  if [ -f "$lf" ]; then
    holder=$(cat "$lf" 2>/dev/null)
    if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
      # Stale lock — reclaim it
      echo $$ > "$lf"
      LOCK_FILE="$lf"
      CHOSEN_PORT="$port"
      break
    fi
  fi
done

if [ -z "$CHOSEN_PORT" ]; then
  echo "ERROR: All Blender MCP ports (${PORTS[*]}) are in use." >&2
  exit 1
fi

echo "Blender MCP using port $CHOSEN_PORT" >&2
export BLENDER_PORT="$CHOSEN_PORT"
exec "C:\Users\tanti\.local\bin\uvx.exe" blender-mcp
