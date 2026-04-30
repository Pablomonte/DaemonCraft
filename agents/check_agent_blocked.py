#!/usr/bin/env python3
"""Check if the Minecraft agent is blocked in a tool loop.

Reads the last N lines of the agent log and determines if the agent
is stuck calling the same failing tool repeatedly (blocked) or making
progress (working).

Exit codes:
    0 = working or inconclusive
    1 = blocked (repetitive failing tool calls detected)
"""

import sys
from pathlib import Path

LOG_FILE = Path.home() / ".local/share/daemoncraft/siqui/logs/Siqui_agent.log"
MAX_LINES = 50
BLOCKED_THRESHOLD = 15


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
        # Extract tool name and whether it had an error
        parts = line.split("⚡", 1)[1].strip().split()
        if not parts:
            continue
        name = parts[0]
        has_error = "[error]" in line
        tool_calls.append((name, has_error))

    if len(tool_calls) < BLOCKED_THRESHOLD:
        return 0

    # Check if the last BLOCKED_THRESHOLD calls are the same tool, all errors
    last_batch = tool_calls[-BLOCKED_THRESHOLD:]
    first_name = last_batch[0][0]

    if all(name == first_name and err for name, err in last_batch):
        print(f"[check] Agent blocked: {BLOCKED_THRESHOLD}x '{first_name}' errors", file=sys.stderr)
        return 1

    # Also block if the last batch is all errors regardless of tool name
    if all(err for _, err in last_batch):
        print(f"[check] Agent blocked: {BLOCKED_THRESHOLD}x consecutive errors", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
