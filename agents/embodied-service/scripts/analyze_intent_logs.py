#!/usr/bin/env python3
"""analyze_intent_logs.py — Quick analysis of intent_verification.jsonl

Prints a summary of:
- Total calls
- Policy_handled vs embodied_succeeded vs embodied_failed
- Per-category success rates
- Most common failure error_types

Usage:
    python analyze_intent_logs.py [PATH_TO_JSONL]

Default path: ~/.local/share/daemoncraft/lab/logs/intent_verification.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    import os
    default_path = os.path.expanduser("~/.local/share/daemoncraft/lab/logs/intent_verification.jsonl")
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(default_path)

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return 1

    total = 0
    policy_handled = 0
    embodied_succeeded = 0
    embodied_failed = 0
    category_counts: Counter = Counter()
    category_success: Counter = Counter()
    category_failures: Counter = Counter()
    error_types: Counter = Counter()
    policy_layers: Counter = Counter()
    language_counts: Counter = Counter()

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            total += 1
            policy_layer = entry.get("policy_layer", "none")
            policy_layers[policy_layer] += 1

            if policy_layer in ("scope", "ambiguity"):
                policy_handled += 1
                continue

            execution_results = entry.get("execution_results", [])
            all_ok = entry.get("all_ok", False)
            category = entry.get("category", "unknown")
            category_counts[category] += 1

            if all_ok:
                embodied_succeeded += 1
                category_success[category] += 1
            else:
                embodied_failed += 1
                category_failures[category] += 1

            for r in execution_results:
                if not r.get("ok", True):
                    et = r.get("error_type", "unknown")
                    error_types[et] += 1

            # Language detection from intent_original if available
            intent_original = entry.get("intent_original", "")
            if any(c in intent_original.lower() for c in "áéíóúñ"):
                language_counts["es"] += 1
            elif intent_original:
                language_counts["en"] += 1

    print("=" * 60)
    print("Intent Verification Log Analysis")
    print("=" * 60)
    print(f"Log file: {log_path}")
    print(f"Total entries: {total}")
    print()
    print("--- Outcomes ---")
    print(f"  Policy handled (scope/ambiguity): {policy_handled}")
    print(f"  Embodied succeeded (all_ok):      {embodied_succeeded}")
    print(f"  Embodied failed:                  {embodied_failed}")
    print()
    print("--- Policy layers ---")
    for layer, count in policy_layers.most_common():
        print(f"  {layer}: {count}")
    print()
    print("--- Per-category success rates ---")
    for cat in sorted(category_counts.keys()):
        total_cat = category_counts[cat]
        ok_cat = category_success[cat]
        fail_cat = category_failures[cat]
        rate = (ok_cat / total_cat * 100) if total_cat > 0 else 0
        print(f"  {cat:20s}  {ok_cat:3d}/{total_cat:3d} OK  ({rate:5.1f}%)  {fail_cat} failed")
    print()
    print("--- Most common failure error_types ---")
    for et, count in error_types.most_common(10):
        print(f"  {et}: {count}")
    print()
    print("--- Language distribution ---")
    for lang, count in language_counts.most_common():
        print(f"  {lang}: {count}")
    print()
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
