# DaemonCraft — Architecture

Last updated: 2026-05-10

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MINECRAFT SERVER                             │
│  daemoncraft.service (Docker: Purpur 1.21.11, port 25565)           │
│  Plugins: SkinsRestorer, Citizens, LuckPerms, CoreProtect...         │
└──────────┬──────────────────────────────────────────┬───────────────┘
           │ TCP                                       │ TCP
           ▼                                           ▼
┌──────────────────────┐                   ┌──────────────────────┐
│   Steve's Body       │                   │   gAndy's Body       │
│   bot/server.js      │                   │   bot/server.js      │
│   port 3001          │                   │   port 3002          │
│   Mineflayer API     │                   │   Mineflayer API     │
│   WebSocket :3001/ws │                   │   WebSocket :3002/ws │
│   Dashboard :3001/db │                   │   Dashboard :3002/db │
└──┬────────┬──────────┘                   └──┬────────┬──────────┘
   │        │                                  │        │
   │ WS     │ HTTP                             │ WS     │ HTTP
   ▼        ▼                                  ▼        ▼
┌──────────────┐                          ┌──────────────┐
│ agent_loop.py│                          │ agent_loop.py│
│ heartbeat    │                          │ heartbeat    │
│ 7s tick      │                          │ 7s tick      │
│ plan exec    │                          │ plan exec    │
└──────┬───────┘                          └──────┬───────┘
       │ POST /heartbeat/context                │
       │ POST /intent to embodied               │
       ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EMBODIED SERVICE (:7790)                          │
│  index.js — HTTP POST /intent                                       │
│  • Compone world_state desde bot/server.js                           │
│  • Llama a Gemma-Andy (Ollama @ 10.10.20.1:11434)                   │
│  • Despacha tool_calls al bot/server.js correspondiente              │
│  • Auto-retry con previous_error (1 intento de recovery)             │
└─────────────────────────────────────────────────────────────────────┘
       ▲                                         ▲
       │ embodied_plan(intent=...)               │
       │                                         │
┌──────┴───────┐                          ┌──────┴───────┐
│ hermes-gw    │                          │ hermes-gw    │
│ @steve       │                          │ @gandy       │
│              │                          │              │
│ LLM cognition│                          │ LLM cognition│
│ MiniMax-M2.7 │                          │ MiniMax-M2.7 │
│              │                          │              │
│ SOUL.md      │                          │ SOUL.md      │
│ config.yaml  │                          │ config.yaml  │
│ .env         │                          │ .env         │
│ busy: steer  │                          │ busy: steer  │
└──────────────┘                          └──────────────┘
```

## Data Flow

### 1. Chat (Player → Bot Response)

```
Player types "@steve seguime"
  → Minecraft chat
  → bot/server.js WebSocket broadcast
  → agent_loop.py WebSocket listener detects chat
  → Gateway (@steve) receives chat via daemoncraft adapter
  → LLM processes: "@steve" = steer (queued, no interrupt)
                    "@steve!" = interrupt (aborts current turn)
  → LLM calls embodied_plan(intent="Follow the player")
  → Embodied service: world_state → Gemma-Andy → tool_calls
  → bot/server.js executes: goto, follow, etc.
  → LLM responds to player: "voy"
  → Gateway sends response back to Minecraft chat
```

### 2. Autonomous Plan Execution

```
LLM writes workspace/plan.json  (strategic multi-step plan)
  → agent_loop.py detects plan on next tick (~7s)
  → Loads step N: { intent, verify }
  → POST /intent to embodied service
  → Gemma-Andy plans + executes body-level tool_calls
  → agent_loop.py verifies step result against verify spec
  → Success → advance to step N+1
  → Failure → retry (exponential backoff), max_retries → escalate
  → Plan complete → wake LLM via gateway
  → Dashboard Plan panel updates in real-time via heartbeat
```

### 3. Idle Heartbeat (No Plan, No Chat)

```
agent_loop.py 7s tick
  → POST /heartbeat/context to bot/server.js
  → Bot broadcasts to dashboard (status, inventory, plan)
  → Body session injected into gateway context
  → LLM stays dormant (context-only, no turn triggered)
```

## Key Decisions

| Decision | Date | Rationale |
|---|---|---|
| Path B (Embodied Service) | 2026-05-03 | Ontological: body as separate entity. Gemma-Andy handles execution, MiniMax handles strategy. |
| Per-agent gateways | 2026-05-10 | Each bot gets its own `hermes-gateway@<name>.service` with isolated SOUL, config, .env |
| `busy_input_mode: steer` | 2026-05-10 | @name → steer (no interrupt), @name! → interrupt |
| Multi-bot dispatcher | 2026-05-10 | Per-request `bot_api_url`, mutable currentBotUrl pattern |
| Auto-retry with previous_error | 2026-05-10 | 1 recovery attempt with independent 30s timeout |
| Scan via find_blocks | 2026-05-10 | Efficient unlimited-range block search instead of brute-force |
| Plan system restored | 2026-05-10 | LLM creates plan.json, loop executes, dashboard shows progress |
| Template backport rule | 2026-05-10 | Every runtime change MUST update source templates |

## Services

| Service | Purpose | Port | Managed by |
|---|---|---|---|
| `daemoncraft.service` | Minecraft server (Docker) | 25565 | systemd |
| `daemoncraft-cast.service` | Bot launcher + agent_loop heartbeat | — | systemd |
| `hermes-gateway@steve.service` | Steve cognition (LLM) | — | systemd |
| `hermes-gateway@gandy.service` | gAndy cognition (LLM) | — | systemd |
| `embodied-service.service` | Gemma-Andy bridge | 7790 | systemd |
| Ollama (inference01) | Gemma-Andy model | 11434 | remote |

## File Locations

| Component | Path |
|---|---|
| Steve workspace | `~/agents/steve/` |
| Steve config | `~/agents/steve/hermes-home/config.yaml` |
| Steve SOUL | `~/agents/steve/hermes-home/SOUL.md` |
| Steve .env | `~/agents/steve/hermes-home/.env` |
| Steve plan | `~/agents/steve/workspace/plan.json` |
| gAndy workspace | `~/agents/gandy/` |
| Project repo | `~/Projects/DaemonCraft/` |
| Embodied service | `~/Projects/DaemonCraft/agents/embodied-service/` |
| Gateway adapter | `~/.hermes/hermes-agent/gateway/platforms/daemoncraft.py` |
| SOUL templates | `~/Projects/DaemonCraft/agents/SOUL-base.md` |
| Cast config | `~/Projects/DaemonCraft/agents/casts/companion.yaml` |
| Workspace generator | `~/Projects/DaemonCraft/agents/workspace.py` |
