# Gateway & Toolset Separation Architecture

**Status:** canonical (post-incident)  
**Date:** 2026-05-04  
**Replaces:** any ad-hoc decision to add CLI toolsets to Minecraft agents  
**Related:** `daemoncraft-platform-adapter.md`, `MEMORY.md` (Incident: Gateway Crossover)

---

## The Core Rule

> **A Minecraft bot is not a coding assistant. A coding assistant is not a Minecraft bot.**
> 
> Their toolsets must never mix.

Hermes is a multi-platform agent framework. It supports Telegram, Discord, CLI/TUI, and DaemonCraft (Minecraft). Each platform has a **platform toolset** — the set of tools the agent is allowed to use when operating on that platform.

The incident of 2026-05-04 proved that adding CLI/TUI toolsets (`research`, `terminal`, `file`, `web`, `browser`, `code_execution`, `delegation`) to the DaemonCraft platform causes the agent to:
- Lose its Minecraft identity and adopt a terminal/IDE persona
- Attempt to spawn browser sessions and delegate coding tasks
- Send messages to the wrong platform (e.g., Telegram instead of Minecraft chat)
- Enter crash loops when tools fail due to missing CLI context

---

## Two Gateways, One Binary

Both the Telegram gateway and the DaemonCraft gateway run `hermes gateway run`. They are distinguished by **platform configuration**, not by binary.

| Aspect | Hermes CLI/TUI Gateway | DaemonCraft Bot Gateway |
|--------|----------------------|------------------------|
| systemd service | `hermes-gateway.service` | `siqui.service`, `pamplinas.service`, etc. |
| User | `hermes` | `siqui` |
| `HERMES_HOME` | `/var/lib/hermes` | `/home/siqui/.hermes` |
| Platforms enabled | `telegram`, `discord`, `cli` | `daemoncraft` |
| Toolsets | `research`, `terminal`, `file`, `web`, `browser`, `code_execution`, `delegation`, `messaging`, `memory`, `skills` | `minecraft`, `messaging`, `vision`, `clarify` |
| Bridge | `127.0.0.1:8088` (shared) | Consumes bot API WebSocket only |
| Parent agent | Yes — spawns sub-agents | No — single-session per bot |

The bridge on `8088` is shared infrastructure, but each gateway only uses it for its own platform adapters. There is no cross-routing.

---

## Toolset Matrix

### Forbidden for DaemonCraft

These toolsets require a CLI/TUI environment and MUST NOT be assigned to any DaemonCraft agent or platform:

| Toolset | Why forbidden |
|---------|--------------|
| `research` | Spawns `run_research` which creates sub-agent worker processes expecting terminal/file/web tools |
| `terminal` | Minecraft bots have no shell access |
| `file` | Profile workspace is not a general filesystem |
| `web` | No browser in Minecraft context |
| `browser` | No browser in Minecraft context |
| `code_execution` | No Python/Node runtime for arbitrary code |
| `delegation` | Sub-agents inherit wrong platform context |
| `cronjob` | Scheduled jobs make no sense for a real-time game bot |
| `skills` | Skill creation requires terminal/file tools |

### Allowed for DaemonCraft

| Toolset | Purpose |
|---------|---------|
| `minecraft` | Core bot tools: perceive, move, build, mine, chat, command |
| `messaging` | `send_message` for out-of-game notifications (Telegram screenshots) |
| `vision` | Screenshot analysis via Gemini Flash |
| `clarify` | Ask-the-user clarification when intent is ambiguous |

### Optional with caution

| Toolset | Condition |
|---------|-----------|
| `memory` | Only if memory operations are scoped to Minecraft context |
| `session_search` | Only if search is scoped to the bot's own session |

---

## Configuration Layers

Toolsets can be configured at three layers. All three must be checked:

### 1. Global platform toolsets (`~/.hermes/config.yaml`)

```yaml
platform_toolsets:
  daemoncraft:
    - minecraft
    - clarify
    - messaging
    - vision
```

**This affects ALL agents on the DaemonCraft platform.** A single wrong entry here breaks every bot.

### 2. Cast agent extra toolsets (`agents/casts/<cast>.yaml`)

```yaml
agents:
  - name: Siqui
    extra_toolsets:
      - vision   # ✅ allowed
      # - research  # ❌ NEVER
```

These are merged into the profile config by `daemoncraft.py setup_agent_profile()`.

### 3. Profile config (`~/.hermes/profiles/<name>/config.yaml`)

```yaml
toolsets:
  - minecraft
  - messaging
  - vision
platform_toolsets:
  cli:
    - minecraft
    - clarify
    - messaging
    - vision
```

If `research` appears here, it was either:
- Added by `daemoncraft.py` because the cast YAML had it in `extra_toolsets`
- Added manually (don't do this)
- Added by a Hermes update or migration script

---

## Prevention Checklist

Before adding any toolset to a DaemonCraft cast or profile:

1. [ ] Is the tool listed in the **Allowed** section above?
2. [ ] Does the tool require a terminal, browser, or filesystem?
3. [ ] Does the tool spawn sub-agents or delegate tasks?
4. [ ] Have you checked `platform_toolsets.daemoncraft` in `~/.hermes/config.yaml`?
5. [ ] Have you checked the profile's `config.yaml`?
6. [ ] Have you grepped the profile's `SOUL.md` for CLI/TUI instructions?

If any answer is "yes" to questions 2 or 3, **do not add the toolset**.

---

## Recovery Procedure (if crossover happens)

1. **Stop the affected gateway**: `sudo systemctl stop siqui.service`
2. **Audit configs**:
   - `~/.hermes/config.yaml` → check `platform_toolsets.daemoncraft`
   - `~/.hermes/profiles/siqui/config.yaml` → check `toolsets` and `platform_toolsets.cli`
   - `agents/casts/siqui.yaml` → check `extra_toolsets`
3. **Remove forbidden toolsets** from all three locations
4. **Verify model consistency**: profile model must match global model (or be intentionally different with user approval)
5. **Rebuild profile SOUL**: delete `~/.hermes/profiles/siqui/SOUL.md` and run `daemoncraft.py start siqui` (or rebuild manually from `SOUL-base.md` + cast SOUL + character prompt)
6. **Restart gateway**: `sudo systemctl start siqui.service`
7. **Verify in logs**: grep for `Toolsets:` — should show only `minecraft`, `messaging`, `vision` (and optionally `clarify`)

---

## Related Documents

- `daemoncraft-platform-adapter.md` — WebSocket adapter design, session mapping, TTS integration
- `chat-output-pipeline-v1.md` — Chat formatting, fragmentation, pipeline concerns
- `MEMORY.md` — Incident narrative and debugging findings
