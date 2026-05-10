# DaemonCraft — Development

Last updated: 2026-05-10

## Golden Rules

### 1. Template Backport (CRITICAL)

**Every runtime change MUST be backported to source templates.**

| Runtime file | Backport to |
|---|---|
| `~/agents/<name>/hermes-home/config.yaml` | `workspace.py` config dict |
| `~/agents/<name>/hermes-home/SOUL.md` | `SOUL-base.md` + `prompts/<template>.md` |
| `~/agents/<name>/hermes-home/.env` | `workspace.py` env_content f-string |
| Hermes gateway adapter | `~/.hermes/hermes-agent/` + workspace copy |

**Without backporting, `daemoncraft.py update companion` wipes everything.**

### 2. Never create .env manually

`workspace.py` inherits provider API keys from `~/.hermes/.env` automatically. Manual creation always misses keys.

### 3. Never edit deploy directly

Work in `~/Projects/DaemonCraft/` or `~/Projects/hermes-agent/`. Deploy to `~/.hermes/hermes-agent/` only via `cp` or `daemoncraft.py update`.

### 4. Documentation alongside code

Every architecture decision, new feature, or changed convention gets documented in `docs/`. Update docs in the same commit as the code change.

## Repository Structure

```
~/Projects/DaemonCraft/
├── agents/
│   ├── daemoncraft.py          # Cast launcher: start/stop/update/status
│   ├── workspace.py            # Per-agent workspace bootstrap (.env, config, SOUL, venv)
│   ├── agent_loop.py           # Heartbeat injector + autonomous plan execution
│   ├── plan_schema.py          # Plan data model (Plan, Step, VerifySpec)
│   ├── SOUL-base.md            # Universal agent operating manual (→ SOUL.md)
│   ├── SOUL-minecraft.md       # Legacy companion SOUL (superseded by SOUL-base.md)
│   ├── bot/
│   │   ├── server.js           # Mineflayer HTTP API + WebSocket + Dashboard
│   │   └── dashboard.html      # Single-page dashboard UI
│   ├── embodied-service/
│   │   ├── index.js            # HTTP POST /intent → Gemma-Andy bridge
│   │   ├── lib/
│   │   │   ├── ollama.js       # Ollama API client (endpoint, model, serialization)
│   │   │   ├── schema.js       # Tool schema loader + executor filter
│   │   │   ├── dispatcher.js   # Canonical tool → bot/server.js action mapper
│   │   │   ├── refs.js         # Reference resolvers (blocks, entities, coords)
│   │   │   ├── world_state.js  # World state composer (7 canonical fields)
│   │   │   ├── parser.js       # Gemma-Andy response parser (<think> strip)
│   │   │   ├── mitigations.js  # Post-parse regression mitigations
│   │   │   └── defaults.js     # Guardian constraints, default tools
│   │   ├── config.json         # Tunable parameters (scan radius, timeout, etc.)
│   │   └── systemd/            # Systemd unit files
│   ├── casts/
│   │   └── companion.yaml      # Cast config: model, provider, port, template
│   └── prompts/
│       └── landfolk/           # Character-specific personality layers
├── docs/
│   ├── ARCHITECTURE.md         # System architecture + flow diagrams
│   ├── OPERATIONS.md           # How to run, troubleshoot, manage
│   ├── DEVELOPMENT.md          # This file
│   └── GEMMA_ANDY_AUDIT.md     # Mariano's design vs our implementation
└── MEMORY.md                   # Project memory (agent state, decisions, pitfalls)
```

## Key Flows During Development

### Changing agent behavior (SOUL, config, tools)

1. Edit source templates (`SOUL-base.md`, `workspace.py`, `prompts/*.md`)
2. Run `daemoncraft.py update companion`
3. Test with a chat message

### Changing embodied service (dispatch, scanning, recovery)

1. Edit files in `agents/embodied-service/`
2. `systemctl --user restart embodied-service`
3. Test with `curl -X POST http://localhost:7790/intent ...`

### Changing gateway adapter (chat handling, @mentions, interrupt)

1. Edit `~/.hermes/hermes-agent/gateway/platforms/daemoncraft.py`
2. Copy to workspace: `cp ~/.hermes/hermes-agent/gateway/platforms/daemoncraft.py ~/Projects/hermes-agent/gateway/platforms/daemoncraft.py`
3. `systemctl --user restart hermes-gateway@steve.service hermes-gateway@gandy.service`

### Adding a new agent

1. Add entry to `agents/casts/companion.yaml`
2. Increment port
3. Add systemd unit: `hermes-gateway@<name>.service` (uses template `hermes-gateway@.service`)
4. Run `daemoncraft.py update companion`

## Provider Configuration

- **Model:** MiniMax-M2.7
- **API Mode:** `anthropic_messages` (forced in `workspace.py`)
- **Base URL:** `https://api.minimax.io/anthropic`
- **API Key:** Inherited from `~/.hermes/.env` → `MINIMAX_API_KEY`
- **Gemma-Andy:** `gemma-andy:e4b-v2-2-3-q8_0` on `10.10.20.1:11434` (Ollama)
- **Busy mode:** `steer` (set in `workspace.py` config dict)

## SOUL Composition

Each agent's `SOUL.md` is composed from multiple parts by `daemoncraft.py`:

```
SOUL-base.md          (universal rules, tools, examples)
  + cast-specific SOUL  (from cast YAML, if any)
  + character prompt    (from prompts/<template>.md)
  = ~/agents/<name>/hermes-home/SOUL.md
```

To change behavior for ALL agents: edit `SOUL-base.md`.
To change behavior for one character: edit `prompts/landfolk/<name>.md`.

## Plan System

- **Schema:** `plan_schema.py` — Plan, Step, VerifySpec, PlanState
- **Creation:** LLM writes `workspace/plan.json` via Hermes `write_file` tool
- **Execution:** `agent_loop.py` reads plan, feeds each step to embodied service
- **Verification:** Machine-checkable predicates (inventory_has, position_reached, etc.)
- **Display:** `bot/server.js` `loadPlan()` reads plan.json, broadcasts to dashboard
