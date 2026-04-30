#!/usr/bin/env python3
"""Check if the Minecraft agent is blocked in a tool loop.

Reads the last N lines of the agent log and determines if the agent
is stuck calling the same tool repeatedly (blocked) or making progress (working).

Exit codes:
    0 = working or inconclusive
    1 = blocked (repetitive tool calls detected)
"""

import sys
from pathlib import Path

LOG_FILE = Path.home() / ".local/share/daemoncraft/siqui/logs/Siqui_agent.log"
MAX_LINES = 80
ERROR_THRESHOLD = 7       # 7+ errors of same tool = blocked
REPEAT_THRESHOLD = 20     # 20+ repeats of same tool = blocked (even if no errors)


def main() -> int:
    if not LOG_FILE.exists():
        return 0

    try:
        lines = LOG_FILE.read_text().strip().splitlines()
    except Exception:
        return 0

    recent = lines[-MAX_LINES:] if len(lines) > MAX_LINES else lines

    tool_calls = []
    for line in recent:
        if "⚡" not in line:
            continue
        parts = line.split("⚡", 1)[1].strip().split()
        if not parts:
            continue
        name = parts[0]
        has_error = "[error]" in line
        tool_calls.append((name, has_error))

    if len(tool_calls) < ERROR_THRESHOLD:
        return 0

    # 1) Same tool failing repeatedly
    last_batch = tool_calls[-ERROR_THRESHOLD:]
    first_name = last_batch[0][0]
    if all(name == first_name and err for name, err in last_batch):
        print(f"[check] Agent blocked: {ERROR_THRESHOLD}x '{first_name}' errors", file=sys.stderr)
        return 1

    # 2) Any tools failing repeatedly
    if all(err for _, err in last_batch):
        print(f"[check] Agent blocked: {ERROR_THRESHOLD}x consecutive errors", file=sys.stderr)
        return 1

    # 3) Same tool repeated too many times (even without errors) — e.g. mc_build loops
    if len(tool_calls) >= REPEAT_THRESHOLD:
        repeat_batch = tool_calls[-REPEAT_THRESHOLD:]
        repeat_name = repeat_batch[0][0]
        if all(name == repeat_name for name, _ in repeat_batch):
            print(f"[check] Agent blocked: {REPEAT_THRESHOLD}x '{repeat_name}' loop", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
