# DaemonCraft

Distributed AI-native Minecraft metaverse with persistent AI agents ("Daemons").

## Overview

DaemonCraft is an ecosystem where persistent AI companions live inside Minecraft worlds, interacting with players via chat, building structures, running adventures, and adapting to the world in real-time.

**Current server:** `10.10.20.12:25565` (Java Edition, Bedrock via Geyser on 19132)

## Repository Structure

```
agents/
├── agent_loop.py           # Main agent loop (Hermes framework)
├── daemoncraft.py          # Cast launcher & orchestrator
├── bot/
│   ├── server.js           # Mineflayer bot server (HTTP + WebSocket)
│   ├── lib/
│   │   ├── chat.js         # Chat routing & social graph
│   │   ├── perception.js   # Scene analysis & block memory
│   │   └── action_feedback.js
│   └── test/               # Unit tests
├── hermescraft/
│   ├── chat_policy.py      # Chat formatting & noise filtering (NEW)
│   └── minecraft_tools.py  # Consolidated toolset (mc_build, mc_chat, etc.)
├── prompts/
│   └── rolemaster/
│       ├── siqui.md        # Siqui's personality prompt
│       └── pamplinas.md    # Pamplinas' personality prompt
├── casts/
│   └── siqui.yaml          # Cast configuration
├── blueprints/             # Adventure blueprints (JSON)
└── data/                   # Runtime state (locations, story, registry)

server/                     # Minecraft server config (Phi-Craft modpack)
docker/                     # Docker configurations
```

## Quick Start

```bash
# Start everything (Minecraft server + bot + agent)
./start-dev.sh

# Or start individual components:
cd agents/bot && node server.js                    # Bot server
cd agents && python agent_loop.py --profile siqui  # Agent loop
```

## Development

- **Git feature branches** — never commit directly to `main`
- **Chat Policy** — all chat formatting lives in `agents/hermescraft/chat_policy.py`
- **Tests** — run `python agents/hermescraft/chat_policy.py` for inline tests
- **Wiki** at `~/wiki` for design docs and research

## Phase 0

Current milestone: Siqui Rolemaster Companion  
See `docs/ARCHITECTURE.md` for the full system architecture.
