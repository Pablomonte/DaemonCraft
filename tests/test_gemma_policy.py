#!/usr/bin/env python3
"""Tests for agents/gemma_policy.py — 5-layer Gemma-Andy policy module."""

import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent / "agents"
sys.path.insert(0, str(AGENTS_DIR))

from gemma_policy import GemmaPolicy


# ─── fixtures ──────────────────────────────────────────
def make_policy():
    return GemmaPolicy(player_name="player", bot_name="minecraft_bot")


# ─── L2: Scope filter ──────────────────────────────────────
def test_l2_out_of_scope_joke():
    p = make_policy()
    result = p.execute("Contame un chiste corto")
    assert result["policy_handled"] is True
    assert result["outcome"] == "policy_handled_upstream"
    assert result["policy_layer"] == "scope"
    print("PASS: L2 joke → out_of_scope")


def test_l2_out_of_scope_greeting():
    p = make_policy()
    assert p.is_out_of_scope("Hola, ¿cómo estás?")[0] is True
    print("PASS: L2 greeting → out_of_scope")


def test_l2_in_scope_mining():
    p = make_policy()
    assert p.is_out_of_scope("Mine 1 oak_log")[0] is False
    print("PASS: L2 mining → in scope")


# ─── L3: Ambiguity ───────────────────────────────────────────
def test_l3_ambiguous_something_fun():
    p = make_policy()
    result = p.execute("Hacé algo entretenido")
    assert result["policy_handled"] is True
    assert result["outcome"] == "policy_handled_upstream"
    assert result["policy_layer"] == "ambiguity"
    print("PASS: L3 ambiguous → policy_handled")


def test_l3_ambiguous_wander():
    p = make_policy()
    assert p.is_ambiguous("Andá por ahí")[0] is True
    print("PASS: L3 wander → ambiguous")


def test_l3_not_ambiguous_specific():
    p = make_policy()
    assert p.is_ambiguous("Mine 1 oak_log")[0] is False
    assert p.is_ambiguous("Andá a (302, 67, 200)")[0] is False
    print("PASS: L3 specific commands → not ambiguous")


# ─── L4: Category classification + tool narrowing ──────────────────
def test_l4_category_mining():
    p = make_policy()
    result = p.execute("Mine 1 oak_log")
    assert result["policy_handled"] is False
    assert result["categories"] == ["mining"]
    print("PASS: L4 mining category")


def test_l4_category_equip():
    p = make_policy()
    result = p.execute("Equip torch")
    assert result["categories"] == ["equip"]
    assert result["allowed_tools"] == [["get_inventory", "equip_item", "ask_clarification", "report_execution_error"]]
    print("PASS: L4 equip tools narrow")


def test_l4_category_navigation():
    p = make_policy()
    assert p.classify_category("Andá al jugador") == "navigation"
    print("PASS: L4 navigation category")


def test_l4_category_memory():
    p = make_policy()
    assert p.classify_category("Acordate de esta posición") == "memory"
    print("PASS: L4 memory category")


def test_l4_guardian_aware():
    p = make_policy()
    nav_tools = p.get_allowed_tools("navigation")
    assert "raise_guardian_event" in nav_tools
    eq_tools = p.get_allowed_tools("equip")
    assert "raise_guardian_event" not in eq_tools
    print("PASS: L4 guardian_aware conditional")


def test_l4_default_returns_none():
    p = make_policy()
    assert p.get_allowed_tools("default") is None
    print("PASS: L4 default tools = None")


# ─── L5: Decompose ───────────────────────────────────────────────
def test_l5_decompose_temporal():
    p = make_policy()
    sub = p.decompose(
        "Acordate de esta posición como home, después caminá 8 bloques al oeste, después volvé a home"
    )
    assert len(sub) >= 3, f"expected >=3 sub-intents, got {len(sub)}: {sub}"
    print(f"PASS: L5 temporal decompose ({len(sub)} sub-intents)")


def test_l5_constraints_merged():
    p = make_policy()
    sub = p.decompose("Find and approach the player. Stop within 3 blocks. Avoid hazards.")
    assert len(sub) == 1, f"expected 1 sub-intent (constraints merged), got {len(sub)}: {sub}"
    assert "Stop within 3 blocks" in sub[0]
    assert "Avoid hazards" in sub[0]
    print("PASS: L5 constraints merged into single sub-intent")


def test_l5_and_connector():
    p = make_policy()
    sub = p.decompose("Mine 3 oak_log and craft a crafting table")
    assert len(sub) == 2, f"expected 2 sub-intents, got {len(sub)}: {sub}"
    print("PASS: L5 'and' connector splits correctly")


def test_l5_empty_returns_empty():
    p = make_policy()
    assert p.decompose("") == []
    print("PASS: L5 empty intent → []")


# ─── L1: Normalize ───────────────────────────────────────────────
def test_l1_normalize_remember():
    p = make_policy()
    norm = p.normalize_surface("Acordate de tu posición")
    assert "Remember" in norm
    assert norm.endswith(".")
    print(f"PASS: L1 normalize → {norm!r}")


def test_l1_bare_come_here():
    p = make_policy()
    norm = p.normalize_surface("ven aca")
    assert norm == "Follow the player named player and stay within 3 blocks."
    print(f"PASS: L1 bare-come → {norm!r}")


def test_l1_bare_veni():
    p = make_policy()
    norm = p.normalize_surface("vení")
    assert "Follow the player named player" in norm
    print(f"PASS: L1 bare-vení → {norm!r}")


def test_l1_capitlization_and_period():
    p = make_policy()
    norm = p.normalize_surface("minar 3 oak_log")
    assert norm.startswith("Mine")
    assert norm.endswith(".")
    print(f"PASS: L1 capitalization + period → {norm!r}")


# ─── Orchestrator: execute() ──────────────────────────────────────
def test_execute_empty_intent():
    p = make_policy()
    result = p.execute("")
    assert result["policy_handled"] is False
    assert result["outcome"] == "embodied_ready"
    assert result["sub_intents"] == []
    assert result["categories"] == []
    assert result["allowed_tools"] == []
    print("PASS: execute('') → embodied_ready, empty chains")


def test_execute_mining_with_tools():
    p = make_policy()
    result = p.execute("Mine 1 oak_log")
    assert result["policy_handled"] is False
    assert result["sub_intents"] == ["Mine 1 oak_log."]
    assert result["categories"] == ["mining"]
    assert "mine_block" in result["allowed_tools"][0]
    print("PASS: execute('Mine 1 oak_log') → mining + narrow tools")


def test_execute_multi_step_and():
    p = make_policy()
    result = p.execute("Mine 3 oak_log and craft a crafting table")
    assert result["policy_handled"] is False
    assert len(result["sub_intents"]) == 2
    assert result["categories"][0] == "mining"
    print("PASS: execute multi-step → 2 sub-intents with categories")


# ── Reference cases at policy layer (Layer 2) ─────────────────────
def test_policy_case1_positive():
    p = make_policy()
    result = p.execute("Help the player gather wood before night.")
    assert result["policy_handled"] is False
    assert result["outcome"] == "embodied_ready"
    assert result["categories"] == ["mining"]
    assert "mine_block" in result["allowed_tools"][0]
    assert "ask_clarification" in result["allowed_tools"][0]
    print("PASS: policy case 1 → mining, narrow tools, signals included")


def test_policy_case2_ambiguous_passes_through():
    p = make_policy()
    # Exact English phrase from reference case 2; current L3 regex targets
    # Spanish/colloquial vagueness tokens, so this passes through.
    result = p.execute("Build it over there.")
    assert result["policy_handled"] is False
    assert result["outcome"] == "embodied_ready"
    assert result["categories"] == ["build"]
    assert "place_block" in result["allowed_tools"][0]
    print("PASS: policy case 2 → build, passes through (deixis not in L3 regex)")


def test_policy_case2_ambiguous_l3_detected():
    p = make_policy()
    # L3 ambiguity detection for canonical vague phrases
    result = p.execute("Hacé algo entretenido")
    assert result["policy_handled"] is True
    assert result["outcome"] == "policy_handled_upstream"
    assert result["policy_layer"] == "ambiguity"
    assert "algo" in result["policy_reason"]
    print("PASS: policy case 2 (L3) → ambiguity detected upstream")


def test_policy_case3_unsafe():
    p = make_policy()
    result = p.execute("Place TNT next to the village fountain.")
    assert result["policy_handled"] is False
    assert result["outcome"] == "embodied_ready"
    assert result["categories"] == ["build"]
    # Build category tools: scan, goto, place_block, equip, inventory, signals
    assert "place_block" in result["allowed_tools"][0]
    assert "ask_clarification" in result["allowed_tools"][0]
    # Note: raise_guardian_event is only added to GUARDIAN_AWARE_CATEGORIES
    # (navigation, combat, default). Build relies on the model's guardian
    # constraint awareness and the caller's guardian_constraints field.
    print("PASS: policy case 3 → build, tools narrowed")


def test_policy_case4_recovery():
    p = make_policy()
    result = p.execute("Go to the player.")
    assert result["policy_handled"] is False
    assert result["outcome"] == "embodied_ready"
    assert result["categories"] == ["navigation"]
    assert "goto" in result["allowed_tools"][0]
    assert "raise_guardian_event" in result["allowed_tools"][0]
    print("PASS: policy case 4 → navigation, recovery tools available")


def test_policy_case5_out_of_scope():
    p = make_policy()
    result = p.execute("Tell me a joke.")
    assert result["policy_handled"] is True
    assert result["outcome"] == "policy_handled_upstream"
    assert result["policy_layer"] == "scope"
    assert "joke" in result["policy_reason"]
    assert result["sub_intents"] == []
    assert result["allowed_tools"] == []
    print("PASS: policy case 5 → scope blocked upstream")


# ── Main runner ──────────────────────────────────────────────
def run_all():
    tests = [
        test_l2_out_of_scope_joke,
        test_l2_out_of_scope_greeting,
        test_l2_in_scope_mining,
        test_l3_ambiguous_something_fun,
        test_l3_ambiguous_wander,
        test_l3_not_ambiguous_specific,
        test_l4_category_mining,
        test_l4_category_equip,
        test_l4_category_navigation,
        test_l4_category_memory,
        test_l4_guardian_aware,
        test_l4_default_returns_none,
        test_l5_decompose_temporal,
        test_l5_constraints_merged,
        test_l5_and_connector,
        test_l5_empty_returns_empty,
        test_l1_normalize_remember,
        test_l1_bare_come_here,
        test_l1_bare_veni,
        test_l1_capitlization_and_period,
        test_execute_empty_intent,
        test_execute_mining_with_tools,
        test_execute_multi_step_and,
        test_policy_case1_positive,
        test_policy_case2_ambiguous_passes_through,
        test_policy_case2_ambiguous_l3_detected,
        test_policy_case3_unsafe,
        test_policy_case4_recovery,
        test_policy_case5_out_of_scope,
        test_strategy_map_returns_correctly,
        test_needs_setup_for_build,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__}: {e}")
            failed += 1
    print()
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
