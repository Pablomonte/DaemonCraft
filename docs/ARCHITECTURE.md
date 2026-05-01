# DaemonCraft Architecture

## System Overview

```
┌─────────────────┐     HTTP/WebSocket      ┌──────────────────┐
│   Agent Loop    │ ◄─────────────────────► │   Bot Server     │
│  (Python/Hermes)│                         │  (Node/Mineflayer)│
└────────┬────────┘                         └────────┬─────────┘
         │                                           │
         │ 1. Receives chat via WebSocket            │ 2. Connects to MC server
         │ 2. Runs AI model (kimi-for-coding)        │ 3. Executes /commands
         │ 3. Calls tools (mc_build, mc_chat...)     │ 4. Sends chat via b.chat()
         │ 4. Posts response to /chat/send           │ 5. Serves screenshots
         │                                           │
         └───────────────────────────────────────────┘
                         Localhost:3002
```

## Chat Pipeline (Consolidated)

**Before the consolidation**, chat logic was scattered across 3 files with contradictory rules:
- `agent_loop.py` — auto-prefixed SAY:, filtered noise, detected Spanish (broken heuristic)
- `server.js` — stripped SAY:, joined verses with spaces, had two modes (tool vs auto)
- `siqui.md` — documented SAY: rules that the model often ignored

**After the consolidation** (April 2026), a single module owns all chat policy:

### `agents/hermescraft/chat_policy.py`

Pure functions, testable offline, zero server dependencies.

```python
filter_noise(text)          # Drop ".", "..", "ok", "hm", short digits
enforce_say_format(text)    # Extract SAY: lines, truncate >180, gentle fallback
detect_language(messages)   # Conservative Spanish detection (no false positives)
```

#### Responsibilities

| Function | What it does | What it does NOT do |
|----------|--------------|---------------------|
| `filter_noise` | Returns `None` for meaningless responses | Never blocks valid short answers |
| `enforce_say_format` | Extracts SAY: lines; auto-prefixes short lines gently | Never drops reasoning blocks silently |
| `detect_language` | Returns `"es"` only for strong indicators (¿, ¡, 3+ letter Spanish words) | Never flags English as Spanish |

### Agent Loop (`agent_loop.py`)

- **Turn 1**: Fetches recent chat history to give the agent context of "what happened while I was away"
- **Chat turns**: Builds prompt with player messages + language hint + formatting mandate
- **Idle turns**: Explicitly tells agent to stay silent if nothing needs attention
- **Loop detection**: `repeat_count` (exact same response), `build_streak` (3+ fills / 5+ places per turn)
- **Guardian**: Runs every 60s via `/command` endpoint (not chat), backs off after 3 failures

### Bot Server (`server.js`)

- **`sendToMcChat(text, {source})`**:
  - `source === "tool"`: trusts agent completely, sends each line as its own fragment (preserves verses)
  - `source !== "tool"`: legacy SAY: filter for backward compatibility with external callers
- **No parsing of SAY:** — no noise filtering, no language detection, no decision-making
- **Only chunking + throttling**: 240 chars max, 5 fragments per 10s window

## Data Flow

### Player sends message

1. Mineflayer receives chat event
2. Bot server adds to `chatLog`, broadcasts via WebSocket
3. Agent loop receives WebSocket message, triggers turn
4. Agent loop builds prompt with recent messages + chat policy hints
5. AI model generates response (reasoning + SAY: lines + commands)
6. Agent loop calls `chat_policy.enforce_say_format()`
7. Valid chat lines posted to `/chat/send`
8. Bot server chunks and delivers to Minecraft

### Screenshot Pipeline

1. Agent calls `mc_screenshot()` → `/action/screenshot`
2. Bot server checks if WebGL viewer is available
3. If available: uses prismarine-viewer + puppeteer (headless Chromium)
4. If not (Pi4/headless): falls back to **top-down block map** via node-canvas
5. Image saved to `/tmp/daemoncraft-screenshots/`, path returned to agent

## Key Design Decisions

### Why consolidate chat policy into a single module?

Before: 3 files with overlapping and contradictory rules. Fixing a bug in one place introduced regressions in another.
After: One module with pure functions, unit tests, and clear contracts.

### Why let the server trust the agent (`source="tool"`)?

The agent has more context (player language, conversation history, story state). The server should not second-guess formatting decisions. This also makes the server simpler and faster.

### Why conservative language detection?

The previous heuristic used single-letter markers ("a", "y", "de") and flagged virtually every English message as Spanish. The new detector only triggers on strong indicators (inverted punctuation, actual Spanish words of 3+ letters).

## Configuration

### Cast YAML (`agents/casts/siqui.yaml`)

```yaml
agents:
  - name: Siqui
    template: rolemaster/siqui
    port: 3002
    model: kimi-for-coding
    provider: kimi-coding
    always_chat: true
    interval: 3           # Seconds between idle turns
    extra_toolsets:
      - vision
    gamemode: creative
    max_chat_chars: 480
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MC_HOST` | `localhost` | Minecraft server IP |
| `MC_PORT` | `25565` | Minecraft server port |
| `MC_USERNAME` | `HermesBot` | Bot username |
| `API_PORT` | `3001` | Bot HTTP API port |
| `MC_ALWAYS_CHAT` | — | Force chat on every turn |

## Testing

### Chat Policy Tests

```bash
cd agents/hermescraft
python chat_policy.py        # Runs inline assertions
```

### Bot Server Tests

```bash
cd agents/bot
npm test                     # Runs Jest tests for chat, perception, action_feedback
```

## Runtime State

| File | Purpose |
|------|---------|
| `~/.local/share/daemoncraft/story.json` | Active story, phases, flags, objectives |
| `~/.local/share/daemoncraft/rolemaster/godmode` | "on" or "off" for guardian |
| `~/.hermes/profiles/siqui/workspace/plan-*.json` | Active agent plan |
| `/tmp/daemoncraft-screenshots/` | Screenshot output directory |

## See Also

- `agents/prompts/rolemaster/siqui.md` — Siqui's personality and behavior rules
- `agents/hermescraft/chat_policy.py` — Chat formatting and filtering logic
- `agents/bot/server.js` — Bot server implementation
- `agents/agent_loop.py` — Main agent event loop
