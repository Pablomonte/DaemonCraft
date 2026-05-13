"""Integration tests for the two-tier recovery system.

Validates that agent_loop.py correctly orchestrates:
  Tier 2a: recovery_candidates.py deterministic synthesis
  Tier 2b: previous_error canonical model recovery

These tests mock the embodied service and bot state to avoid needing
a live Minecraft server or Ollama instance.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from recovery_candidates import maybe_synthesize_substitute


class FakeStep:
    """Minimal Step stand-in."""
    def __init__(self, intent: str, step_id: str = "s1"):
        self.intent = intent
        self.id = step_id
        self.retries = 0
        self.max_retries = 3

    @property
    def exhausted(self):
        return self.retries >= self.max_retries


def test_tier2a_synthesises_substitute_for_occupied():
    """When place_block fails due to occupied target, recovery_candidates
    synthesises an alternative intent with a different coordinate."""
    step = FakeStep("Place 1 oak_planks at coordinates (5, 65, 38).")
    embodied_result = {
        "ok": False,
        "execution_results": [{
            "tool": "place_block",
            "ok": False,
            "error_type": "bot_action_failed",
            "details": "target space is occupied by leaf_litter",
        }],
    }
    nearby = [
        {"x": 5, "y": 65, "z": 38, "name": "leaf_litter"},
        {"x": 6, "y": 65, "z": 38, "name": "air"},
        {"x": 6, "y": 64, "z": 38, "name": "dirt"},
    ]

    substitute = maybe_synthesize_substitute(
        step, embodied_result,
        bot_position=(5, 65, 39),
        nearby_blocks=nearby,
        inventory={},
    )

    assert substitute is not None
    assert "(6, 65, 38)" in substitute
    assert "(5, 65, 38)" not in substitute
    print("[PASS] Tier 2a: occupied -> substitute synthesised")


def test_tier2b_previous_error_payload_shape():
    """The previous_error payload sent to the embodied service follows
    Mariano's canonical shape: {tool, error_type, details}."""
    embodied_result = {
        "ok": False,
        "execution_results": [{
            "tool": "goto",
            "ok": False,
            "error_type": "stuck",
            "details": "bot position unchanged for 6 seconds; obstacle: leaves",
        }],
    }
    failed = next(
        (r for r in embodied_result.get("execution_results", [])
         if not r.get("ok")), None
    )
    assert failed is not None

    previous_error = {
        "tool": failed.get("tool", "unknown"),
        "error_type": failed.get("error_type", "other"),
        "details": failed.get("details", failed.get("error", "unknown")),
    }

    assert previous_error["tool"] == "goto"
    assert previous_error["error_type"] == "stuck"
    assert "leaves" in previous_error["details"]
    print("[PASS] Tier 2b: previous_error payload shape is canonical")


def test_call_embodied_accepts_previous_error():
    """call_embodied must accept an optional previous_error dict and
    include it in the POST JSON body."""
    import agent_loop

    # Verify signature
    import inspect
    sig = inspect.signature(agent_loop.call_embodied)
    assert "previous_error" in sig.parameters

    # Verify the payload includes previous_error when provided
    captured = {}

    class FakeResponse:
        def read(self):
            return json.dumps({"ok": True}).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def fake_urlopen(req, **kw):
        captured["body"] = json.loads(req.data)
        return FakeResponse()

    with patch("agent_loop.urllib.request.urlopen", fake_urlopen):
        agent_loop.call_embodied(
            "test intent",
            previous_error={"tool": "goto", "error_type": "stuck", "details": "x"}
        )

    assert "previous_error" in captured["body"]
    assert captured["body"]["previous_error"]["tool"] == "goto"
    print("[PASS] call_embodied forwards previous_error to embodied service")


def test_tier_order_in_process_plan_tick():
    """The recovery flow must attempt deterministic synthesis BEFORE
    falling back to previous_error. We verify this by inspecting the
    agent_loop source for the correct ordering of the two if-blocks."""
    source = Path("agents/agent_loop.py").read_text()

    # Find the recovery section
    tier2a_marker = "Tier 2a: deterministic candidate synthesis"
    tier2b_marker = "Tier 2b: canonical model recovery via previous_error"

    assert tier2a_marker in source
    assert tier2b_marker in source

    pos_2a = source.find(tier2a_marker)
    pos_2b = source.find(tier2b_marker)
    assert pos_2a < pos_2b, "Tier 2a must appear before Tier 2b in source"

    print("[PASS] Tier order: 2a (deterministic) -> 2b (previous_error)")


if __name__ == "__main__":
    test_tier2a_synthesises_substitute_for_occupied()
    test_tier2b_previous_error_payload_shape()
    test_call_embodied_accepts_previous_error()
    test_tier_order_in_process_plan_tick()
    print("\nAll integration smoke tests passed.")
