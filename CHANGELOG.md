# Changelog

## [2026-05-01] Revert to Kimi OAuth (kimi-for-coding)

### Changed
- **`agents/casts/siqui.yaml`**:
  - Model reverted from `kimi-k2.6` → `kimi-for-coding`
  - Base URL reverted from `api.moonshot.ai/v1` → `api.kimi.com/coding/v1`
- **`daemoncraft.py`** & **`agent_loop.py`** reverted to `53922de` state
  - Removed `model.base_url` write in daemoncraft.py
  - Removed profile `.env` loading and explicit `api_key` pass in agent_loop.py
- **Reason**: `kimi-k2.6` is rejected by `api.kimi.com/coding/v1` with
  `access_terminated_error`. The Kimi CLI OAuth token only works on the Coding
  endpoint, and `kimi-for-coding` is the compatible model for that plan.

### Added
- **`deploy/hermes/profiles/siqui/`** — Versioned reference for the live Hermes profile
  - `config.yaml` (OAuth template)
  - `.env` (`MC_API_URL` only)
  - `README.md` explaining the OAuth flow

### External Changes Documented
- `~/.hermes/profiles/siqui/config.yaml` — managed by daemoncraft.py
- `~/.hermes/profiles/siqui/.env` — managed by daemoncraft.py
- `~/.hermes/profiles/siqui/SOUL.md` — updated 2026-05-01 20:01

---

## [2026-04-30] Chat Pipeline Consolidation

### Added
- **`agents/hermescraft/chat_policy.py`** — Single source of truth for all chat behavior
  - `filter_noise()`: exact-match drop list for meaningless responses
  - `enforce_say_format()`: extracts SAY: lines, truncates >180 chars, gentle auto-prefix fallback
  - `detect_language()`: conservative Spanish detection using ¿/¡ and 3+ letter Spanish words only
  - Inline self-tests (run with `python chat_policy.py`)
- **Startup context** — Agent reads last 15 chat messages on restart to know "what happened while I was away"
- **Idle silence hint** — Agent explicitly told to stay silent if nothing needs attention (prevents random poetic spam)
- **Top-down screenshot fallback** — `node-canvas` block-map for Pi4/headless environments when WebGL is unavailable
- **Configurable turn interval** — `interval` field in cast YAML (default 7s, Siqui uses 3s)

### Changed
- **`agent_loop.py`**:
  - Imports `chat_policy`, removes duplicated `_clean_response_for_chat`
  - Replaces broken Spanish heuristic ("a", "y", "de" flagged everything as Spanish)
  - Removes unused `last_build_coords` variable
  - Guardian uses `/command` endpoint instead of `/chat/send` (no more /gamemode in public chat)
  - `_post_chat` now injects formatting hints into `conversation_history` for next turn
- **`server.js`**:
  - `sendToMcChat` simplified: `source="tool"` trusts agent completely, sends lines as-is
  - `source!="tool"` keeps legacy SAY: filter for backward compatibility
  - Verses preserved: each line becomes its own fragment (no more `join(" ")`)
  - Noise filtering and SAY: parsing removed from server (now in chat_policy)
- **`siqui.md` prompt**:
  - Added explicit `OUTPUT FORMAT` section at end
  - Clear ordering: reasoning → SAY: lines → commands
- **Server migration**: `10.10.20.1` → `10.10.20.12:25565`

### Fixed
- `.` spam in chat (single dots pushing chat up)
- Scoreboard poll commands spamming public chat (`poll_sensors` no longer sends /execute to chat)
- Guardian effect spam (5s → 60s interval, 5min backoff after 3 failures)
- `mc_screenshot` blank images on Pi4 (replaced WebGL pipeline with node-canvas top-down map)
- `sendToMcChat` silently dropping `/tp`, `/fill`, `/setblock` commands

## [2026-04-29] Vision & Loop Detection

### Added
- `mc_screenshot` tool using prismarine-viewer + puppeteer
- `mc_story` blueprint support (`list_blueprints`, `load_blueprint`)
- Repetition loop detection with gentle nudging (no memory wipes)
- `mc_chat` spam detection (>5 calls per turn triggers hint)
- Build loop detection (3+ fills / 5+ places per turn)

### Fixed
- Prompt language reverted to "respond in player's language" (was forcing Argentine Spanish)
- Flight capability restored in Creative Mode
