#!/usr/bin/env python3
"""
Autonomous Plan Execution Loop — DaemonCraft Autonomía Corporal.

CONTRACT (GePeTo review):
  - Steve (MiniMax $) owns: plans, verify predicates, exception handling,
    escalations, replanning. Woken only on hard failures / completion / danger.
  - Gemma-Andy (Ollama $0) owns: execution of concrete intents via tool_calls,
    local world checks, bounded retries within a single step.
  - This loop (autonomous_loop.py) is the GLUE: a finite-state controller that
    reads Steve's plan from workspace/plan.json, feeds steps to Gemma via the
    embodied service, verifies results against Steve's machine-checkable
    predicates, and advances or escalates.

STATES:  idle → executing → blocked → escalated → replanning → completed

COST MODEL:
  - Gemma calls: $0 (local Ollama) → high-frequency (5-10s ticks).
  - Steve calls: $0.03+ (MiniMax) → only on wake_up events.
  - Idle heartbeat: world_state injection via Gemma every 30s ($0).

USAGE:
    python autonomous_loop.py --interval 7
    # Env vars: MC_API_URL, EMBODIED_SERVICE_URL, MC_USERNAME, PLAN_FILE

SAFETY (GePeTo):
  - Structured JSON logging for every decision (replayable audit trail).
  - Explicit danger taxonomy (DangerLevel enum, see plan_schema.py).
  - Retry with exponential backoff; escalation after max_retries.
  - Confidence gate: if operational_risk high/critical → escalate immediately.
  - Type hints everywhere. Python 3.13+.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import urllib.request
from pathlib import Path

# ── Import plan schema from same directory ──
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan_schema import (
    Plan,
    PlanState,
    DangerLevel,
    VerifyType,
    load_plan,
    save_plan,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Environment
# ═══════════════════════════════════════════════════════════════════════════════

MC_API_URL = os.environ.get("MC_API_URL", "http://localhost:3001")
EMBODIED_SERVICE_URL = os.environ.get(
    "EMBODIED_SERVICE_URL", "http://localhost:7790"
)
BOT_USERNAME = os.environ.get("MC_USERNAME", "steve").lower()
AGENT_WORKSPACE = (
    Path.home() / "agents" / BOT_USERNAME / "workspace"
)

# ═══════════════════════════════════════════════════════════════════════════════
# Structured logging — JSON lines (GePeTo: "decision traces, replayable events")
# ═══════════════════════════════════════════════════════════════════════════════

def _log_event(event: str, **fields) -> None:
    """Emit a structured JSON log line. Fields are merged into the record."""
    record = {
        "ts": time.time(),
        "bot": BOT_USERNAME,
        "event": event,
        **fields,
    }
    # JSON-encode and print with flush for systemd/journalctl
    print(json.dumps(record, separators=(",", ":")), flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _post_json(url: str, payload: dict, timeout: float = 30) -> dict:
    """POST JSON. Returns parsed response dict or {'ok': False, '_error': msg}."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {"ok": True}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
            return json.loads(body) if body else {"ok": False, "_error": f"HTTP {e.code}"}
        except Exception:
            return {"ok": False, "_error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "_error": str(e)}


def _get_json(url: str, timeout: float = 5) -> dict:
    """GET JSON. Returns parsed dict or {} on failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except Exception:
        return {}


def _bot_status() -> dict:
    """Fetch bot status (position, health, etc.) from bot server."""
    data = _get_json(f"{MC_API_URL}/status", timeout=5)
    return data.get("data", data)


def _bot_inventory() -> dict:
    """Fetch bot inventory from bot server."""
    data = _get_json(f"{MC_API_URL}/inventory", timeout=5)
    return data.get("data", data)


def _bot_nearby() -> dict:
    """Fetch nearby blocks and entities from bot server."""
    data = _get_json(f"{MC_API_URL}/nearby", timeout=5)
    return data.get("data", data)


# ═══════════════════════════════════════════════════════════════════════════════
# Embodied service — intent execution
# ═══════════════════════════════════════════════════════════════════════════════

_MAX_EMBODIED_RETRIES = 3
_EMBODIED_BACKOFF_BASE = 2.0   # seconds: base^attempt


def call_embodied(intent: str, deadline_s: int = 20) -> dict:
    """
    Call POST /intent on the embodied service.
    Retries with backoff if the service is unreachable.
    Returns the response dict.
    """
    last_error = None
    for attempt in range(_MAX_EMBODIED_RETRIES + 1):
        result = _post_json(
            f"{EMBODIED_SERVICE_URL}/intent",
            {"intent": intent, "deadline_seconds": deadline_s},
            timeout=deadline_s + 10,
        )
        if result.get("ok") is not None:  # valid response (200 or non-200 with JSON)
            return result
        last_error = result.get("_error", "unknown")
        if attempt < _MAX_EMBODIED_RETRIES:
            delay = _EMBODIED_BACKOFF_BASE ** attempt
            _log_event("embodied_retry", attempt=attempt, delay=delay, error=last_error)
            time.sleep(delay)

    _log_event("embodied_unreachable", attempts=_MAX_EMBODIED_RETRIES + 1, last_error=last_error)
    return {"ok": False, "_error": f"embodied_service_unreachable: {last_error}"}


# ═══════════════════════════════════════════════════════════════════════════════
# Verification — machine-checkable predicates (GePeTo)
# ═══════════════════════════════════════════════════════════════════════════════

def verify_step(step_spec, embodied_result: dict) -> tuple[bool, str]:
    """
    Verify a step against the embodied service response and bot state.

    Returns (passed, reason).
    Step is a plan_schema.Step instance.
    """
    verify = step_spec.verify

    # First: check embodied result itself
    if not embodied_result.get("ok"):
        return False, f"embodied_not_ok: {embodied_result.get('_error', embodied_result.get('error', 'unknown'))}"

    execution_results = embodied_result.get("execution_results", [])
    if not execution_results:
        return False, "no_execution_results"

    # Check all tool dispatches succeeded
    failed = [r for r in execution_results if not r.get("ok")]
    if failed:
        reasons = [f"{r.get('tool', '?')}:{r.get('error_type', '?')}" for r in failed]
        return False, f"tool_failures: {', '.join(reasons)}"

    # Per-type verification against bot state
    try:
        if verify.type == VerifyType.INVENTORY_HAS:
            return _verify_inventory_has(verify)

        elif verify.type == VerifyType.POSITION_REACHED:
            return _verify_position_reached(verify)

        elif verify.type == VerifyType.AREA_CLEAR:
            return _verify_area_clear(verify)

        elif verify.type == VerifyType.ENTITY_NEARBY:
            return _verify_entity_nearby(verify)

        elif verify.type == VerifyType.BLOCK_PLACED:
            return _verify_block_placed(verify)

        else:
            return False, f"unknown_verify_type: {verify.type}"

    except Exception as e:
        return False, f"verify_exception: {e}"


def _verify_inventory_has(verify) -> tuple[bool, str]:
    inv = _bot_inventory()
    # Inventory data may be nested: {categories: {materials: {item: count}, ...}} or flat {item: count}
    # Try flat first, then categories
    count = 0
    item = verify.item.lower()

    # Flat inventory (newer bot server format)
    if isinstance(inv, dict):
        for key, val in inv.items():
            if not isinstance(key, str):
                continue
            if key.lower() == item:
                count += int(val) if isinstance(val, (int, float)) else 0

    # Categories format (older bot server)
    categories = inv.get("categories", {})
    if isinstance(categories, dict):
        for cat_name, cat_items in categories.items():
            if isinstance(cat_items, dict):
                for citem, ccount in cat_items.items():
                    if citem.lower() == item:
                        count += int(ccount) if isinstance(ccount, (int, float)) else 0

    passed = count >= verify.count
    reason = f"inventory_has({item}): {count} >= {verify.count} → {'PASS' if passed else 'FAIL'}"
    return passed, reason


def _verify_position_reached(verify) -> tuple[bool, str]:
    status = _bot_status()
    pos = status.get("position", {})
    if not pos:
        return False, "no_position_data"

    bx = pos.get("x", 0)
    bz = pos.get("z", 0)
    by = pos.get("y", 0)

    dist = ((bx - verify.target_x) ** 2 + (bz - verify.target_z) ** 2) ** 0.5
    passed = dist <= verify.max_distance
    reason = (
        f"position_reached: dist={dist:.1f} ≤ {verify.max_distance} "
        f"(bot=({bx:.0f},{by:.0f},{bz:.0f}) target=({verify.target_x},{verify.target_y},{verify.target_z})) "
        f"→ {'PASS' if passed else 'FAIL'}"
    )
    return passed, reason


def _verify_area_clear(verify) -> tuple[bool, str]:
    nearby = _bot_nearby()
    blocks = nearby.get("blocks", nearby.get("nearby_blocks", []))
    if not blocks:
        # No blocks data → cannot verify. Assume NOT clear (unknown state).
        return False, "no_nearby_blocks_data"

    # Blocks above Y in rect (x1..x2, z1..z2)
    blocks_above = 0
    for b in blocks:
        bx = b.get("x", 0)
        bz = b.get("z", 0)
        by_val = b.get("y", 0)
        if (
            verify.x1 <= bx <= verify.x2
            and verify.z1 <= bz <= verify.z2
            and by_val > verify.y
        ):
            blocks_above += 1

    passed = blocks_above <= verify.max_blocks_above
    reason = (
        f"area_clear({verify.x1}..{verify.x2}, {verify.z1}..{verify.z2}, y>{verify.y}): "
        f"{blocks_above} blocks above ≤ {verify.max_blocks_above} → {'PASS' if passed else 'FAIL'}"
    )
    return passed, reason


def _verify_entity_nearby(verify) -> tuple[bool, str]:
    nearby = _bot_nearby()
    entities = nearby.get("entities", nearby.get("nearby_entities", []))
    if not entities:
        return False, f"no_entity({verify.entity_type}): no nearby entities"

    for e in entities:
        etype = (e.get("type") or e.get("name", "")).lower()
        if verify.entity_type.lower() in etype:
            # Entity found. Distance check if position available.
            ex = e.get("x", e.get("position", {}).get("x", 0))
            ez = e.get("z", e.get("position", {}).get("z", 0))
            if ex or ez:  # has position data
                status = _bot_status()
                bx = status.get("position", {}).get("x", 0)
                bz = status.get("position", {}).get("z", 0)
                dist = ((bx - ex) ** 2 + (bz - ez) ** 2) ** 0.5
                passed = dist <= verify.entity_distance
                reason = (
                    f"entity_nearby({verify.entity_type}): dist={dist:.1f} ≤ {verify.entity_distance} "
                    f"→ {'PASS' if passed else 'FAIL'}"
                )
                return passed, reason
            else:
                return True, f"entity_nearby({verify.entity_type}): found (no position data)"

    return False, f"entity_nearby({verify.entity_type}): not found"


def _verify_block_placed(verify) -> tuple[bool, str]:
    # Block placement verification requires checking the specific coordinate.
    # The bot server may have a /block endpoint; otherwise we check nearby_blocks.
    nearby = _bot_nearby()
    blocks = nearby.get("blocks", nearby.get("nearby_blocks", []))

    for b in blocks:
        bx = b.get("x", 0)
        by_val = b.get("y", 0)
        bz = b.get("z", 0)
        bname = (b.get("name") or "").lower()
        if (
            bx == verify.block_x
            and by_val == verify.block_y
            and bz == verify.block_z
        ):
            if verify.block_material:
                material_ok = verify.block_material.lower() in bname
                reason = (
                    f"block_placed({verify.block_x},{verify.block_y},{verify.block_z}): "
                    f"found={bname} match_material={material_ok} → {'PASS' if material_ok else 'FAIL'}"
                )
                return material_ok, reason
            else:
                return True, f"block_placed({verify.block_x},{verify.block_y},{verify.block_z}): found={bname}"

    return False, f"block_placed({verify.block_x},{verify.block_y},{verify.block_z}): not found in nearby_blocks"


# ═══════════════════════════════════════════════════════════════════════════════
# Wake-up Steve — escalate to strategic layer
# ═══════════════════════════════════════════════════════════════════════════════

def wake_steve(reason: str, step_id: int | None = None, detail: str = "") -> bool:
    """
    Wake Steve (MiniMax) via the bot server's heartbeat/context endpoint.

    The gateway adapter picks up the wake_up event and interrupts/schedules
    Steve's next turn for strategic intervention.
    """
    payload = {
        "type": "wake_up",
        "reason": reason,
        "step_id": step_id,
        "detail": detail,
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{MC_API_URL}/agent/wake",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except Exception as e:
        _log_event("wake_steve_failed", reason=reason, error=str(e))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Finite-State Controller — the core loop
# ═══════════════════════════════════════════════════════════════════════════════

def _check_danger(embodied_result: dict) -> DangerLevel | None:
    """Extract danger level from embodied service response. Returns None if safe."""
    plan = embodied_result.get("plan", {})
    risk_str = plan.get("operational_risk", "")
    if not risk_str or risk_str == "none":
        return None
    return DangerLevel.parse_risk(risk_str)


def process_tick(plan: Plan, now: float) -> Plan:
    """
    Execute one tick of the autonomous plan execution loop.

    Pure function: reads plan state, acts, returns updated plan.
    Side-effects: HTTP calls to embodied service and bot server.
    """
    # ── State: IDLE → EXECUTING ──
    if plan.state == PlanState.IDLE:
        _log_event("plan_start", goal=plan.goal, steps=len(plan.steps))
        plan.state = PlanState.EXECUTING
        plan.started_at_ts = now
        plan.last_advance_ts = now
        save_plan(plan)

    # ── State: COMPLETED → stay silent ──
    if plan.state == PlanState.COMPLETED:
        return plan

    # ── State: ESCALATED → wait for Steve ──
    if plan.state == PlanState.ESCALATED:
        return plan  # Steve must replan or abort. Loop does nothing.

    # ── State: BLOCKED → check timeout, maybe escalate ──
    if plan.state == PlanState.BLOCKED:
        if plan.timed_out(now):
            _log_event("plan_timeout", goal=plan.goal, state="blocked",
                       elapsed=now - plan.last_advance_ts)
            wake_steve("plan_timeout", detail=f"No advance in {plan.hard_timeout_s}s")
            plan.state = PlanState.ESCALATED
            save_plan(plan)
        return plan

    # ── State: EXECUTING ──
    if plan.state != PlanState.EXECUTING:
        return plan

    # Plan done?
    if plan.done:
        _log_event("plan_complete", goal=plan.goal, steps=len(plan.steps),
                   elapsed=now - plan.started_at_ts)
        plan.state = PlanState.COMPLETED
        save_plan(plan)
        wake_steve("plan_complete", detail=f"Goal '{plan.goal}' completed")
        return plan

    # Plan timeout?
    if plan.timed_out(now):
        _log_event("plan_timeout", goal=plan.goal, state="executing",
                   elapsed=now - plan.last_advance_ts)
        wake_steve("plan_timeout", detail=f"No advance in {plan.hard_timeout_s}s")
        plan.state = PlanState.ESCALATED
        save_plan(plan)
        return plan

    # Execute current step
    step = plan.current
    if step is None:
        # Shouldn't happen (guarded by plan.done above), but be safe
        plan.state = PlanState.BLOCKED
        save_plan(plan)
        return plan

    _log_event("step_start", step_id=step.id, intent=step.intent[:120],
               retry=step.retries, max_retries=step.max_retries)

    # Call embodied service
    t0 = time.time()
    embodied_result = call_embodied(step.intent)
    elapsed = time.time() - t0

    # ── Confidence gate (GePeTo): check danger BEFORE acting on result ──
    danger = _check_danger(embodied_result)
    if danger is not None:
        _log_event("danger_detected", step_id=step.id, danger=danger.value,
                   is_critical=danger.is_critical, elapsed=elapsed)
        if danger.is_critical:
            plan.state = PlanState.ESCALATED
            save_plan(plan)
            wake_steve("danger_critical", step_id=step.id,
                       detail=f"Danger: {danger.value}")
            return plan
        else:
            # Non-critical danger: log but continue; Steve decides on wake
            wake_steve("danger_detected", step_id=step.id,
                       detail=f"Danger: {danger.value} (non-critical, loop continues)")

    # ── Verify ──
    t0_verify = time.time()
    passed, reason = verify_step(step, embodied_result)
    verify_elapsed = time.time() - t0_verify

    _log_event("step_verify", step_id=step.id, passed=passed, reason=reason,
               embodied_elapsed=elapsed, verify_elapsed=verify_elapsed,
               danger=danger.value if danger else None)

    if passed:
        # ── Success: advance ──
        plan.current_step += 1
        plan.last_advance_ts = now
        step.retries = 0  # reset for next time
        _log_event("step_advance", step_id=step.id,
                   next_step=plan.current_step, remaining=len(plan.steps) - plan.current_step)

        if plan.done:
            plan.state = PlanState.COMPLETED
            save_plan(plan)
            wake_steve("plan_complete", detail=f"Goal '{plan.goal}' completed")
            return plan

        save_plan(plan)
        return plan

    # ── Failed: retry or escalate ──
    step.retries += 1

    if step.exhausted:
        _log_event("step_exhausted", step_id=step.id, retries=step.retries,
                   max_retries=step.max_retries, reason=reason)
        plan.state = PlanState.BLOCKED
        save_plan(plan)
        wake_steve("step_failed", step_id=step.id,
                   detail=f"Step {step.id} exhausted ({step.retries}/{step.max_retries}): {reason}")
        return plan

    # Retry with backoff
    backoff = step.next_backoff_seconds
    _log_event("step_retry", step_id=step.id, retries=step.retries,
               max_retries=step.max_retries, backoff=backoff, reason=reason)
    plan.last_advance_ts = now  # reset timeout clock on retry
    save_plan(plan)
    # Backoff is applied by the caller (the main loop)
    return plan


# ═══════════════════════════════════════════════════════════════════════════════
# Main loop
# ═══════════════════════════════════════════════════════════════════════════════

_shutdown_flag = False


def _on_shutdown(signum, frame):
    global _shutdown_flag
    _shutdown_flag = True
    _log_event("shutdown_signal", signal=signum)


def run_autonomous_loop(interval: float = 7.0):
    """
    Run the autonomous plan execution loop.

    Every `interval` seconds:
      1. Load plan from workspace/plan.json
      2. If plan exists and is in EXECUTING state, process one tick
      3. Save plan back to disk

    If no plan or plan is IDLE: do nothing (Steve hasn't created one yet).
    Future: inject world_state heartbeat via Gemma every 30s when idle.
    """
    signal.signal(signal.SIGTERM, _on_shutdown)
    signal.signal(signal.SIGINT, _on_shutdown)

    _log_event("loop_start", interval=interval, mc_api_url=MC_API_URL,
               embodied_service_url=EMBODIED_SERVICE_URL, bot=BOT_USERNAME)

    tick_count = 0
    idle_count = 0
    IDLE_HEARTBEAT_EVERY = max(1, int(30 / interval))  # ~30s for idle heartbeat

    while not _shutdown_flag:
        now = time.time()
        tick_count += 1

        plan = load_plan()

        if plan is None:
            # No plan yet. Idle heartbeat every ~30s.
            idle_count += 1
            if idle_count >= IDLE_HEARTBEAT_EVERY:
                idle_count = 0
                _log_event("idle_heartbeat", tick=tick_count)
                # Inject world_state via Gemma (no-op for now; gateway handles this)
            time.sleep(interval)
            continue

        idle_count = 0  # reset idle counter when plan exists

        # Process one tick
        try:
            plan = process_tick(plan, now)
        except Exception as e:
            _log_event("tick_error", error=str(e), step=plan.current_step if plan else None)
            # Don't crash the loop — continue next tick
            time.sleep(interval)
            continue

        # Apply backoff if current step is retrying
        if plan.state == PlanState.EXECUTING and plan.current and plan.current.retries > 0:
            backoff = plan.current.next_backoff_seconds
            if backoff > interval:
                _log_event("backoff_sleep", seconds=backoff, step_id=plan.current.id)
                time.sleep(backoff)
                continue

        time.sleep(interval)

    _log_event("loop_exit", tick_count=tick_count)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="DaemonCraft Autonomous Plan Execution Loop — Autonomía Corporal"
    )
    parser.add_argument(
        "--interval", type=float, default=7.0,
        help="Seconds between ticks (default: 7.0; 5-10s recommended)"
    )
    parser.add_argument(
        "--embodied-url", default="",
        help="Override EMBODIED_SERVICE_URL (default: http://localhost:7790)"
    )
    parser.add_argument(
        "--mc-url", default="",
        help="Override MC_API_URL (default: http://localhost:3001)"
    )
    parser.add_argument(
        "--plan-file", default="",
        help="Override PLAN_FILE path (default: ~/agents/<name>/workspace/plan.json)"
    )
    args = parser.parse_args()

    # Override env vars from CLI if provided
    global EMBODIED_SERVICE_URL, MC_API_URL
    if args.embodied_url:
        EMBODIED_SERVICE_URL = args.embodied_url
    if args.mc_url:
        MC_API_URL = args.mc_url
    if args.plan_file:
        os.environ["PLAN_FILE"] = args.plan_file

    run_autonomous_loop(args.interval)


if __name__ == "__main__":
    main()
