"""
Search conversation transcripts for Write/Edit calls on a specific file.

Usage:
    python scripts/search_transcripts.py retarget_export
    python scripts/search_transcripts.py retarget_export --full
"""

import json
import sys
import glob
import os

search_term = sys.argv[1] if len(sys.argv) > 1 else "retarget_export"
show_full = "--full" in sys.argv

transcript_dir = os.path.expanduser(r"~\.claude\projects\C--dev-loracomp3")
transcripts = sorted(glob.glob(os.path.join(transcript_dir, "*.jsonl")))

print(f"Searching for '{search_term}' in {len(transcripts)} transcripts\n")

for tpath in transcripts:
    fname = os.path.basename(tpath)[:12]
    mtime = os.path.getmtime(tpath)
    from datetime import datetime
    ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

    found = 0
    with open(tpath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f):
            try:
                entry = json.loads(line)
            except:
                continue

            if not isinstance(entry, dict):
                continue

            content = entry.get("content", "")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue

                tool = block.get("name", "")
                inp = block.get("input", {})
                inp_str = json.dumps(inp)

                if search_term not in inp_str:
                    continue

                if tool in ("Write", "Edit"):
                    fp = inp.get("file_path", "")
                    if found == 0:
                        print(f"=== {fname} ({ts}) ===")
                    found += 1

                    if tool == "Write":
                        content_text = inp.get("content", "")
                        print(f"\n  [{found}] Line {line_num}: WRITE -> {fp}")
                        print(f"      Length: {len(content_text)} chars")
                        if show_full:
                            print("--- FULL CONTENT ---")
                            print(content_text)
                            print("--- END ---")
                        else:
                            # Show first 500 chars
                            preview = content_text[:500]
                            print(f"      Preview:\n{preview}")
                            if len(content_text) > 500:
                                print(f"      ... ({len(content_text) - 500} more chars, use --full to see all)")

                    elif tool == "Edit":
                        old = inp.get("old_string", "")
                        new = inp.get("new_string", "")
                        print(f"\n  [{found}] Line {line_num}: EDIT -> {fp}")
                        print(f"      Old ({len(old)} chars): {old[:200]}")
                        print(f"      New ({len(new)} chars): {new[:200]}")

    if found > 0:
        print(f"\n  Total: {found} operations\n")
