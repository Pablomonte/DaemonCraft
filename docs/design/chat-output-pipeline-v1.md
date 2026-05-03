# DaemonCraft Chat Output Pipeline — Design v1

**Status:** approved for implementation  
**Date:** 2026-04-29  
**Author:** systems architect (Claude Opus 4.7), adopted by DaemonCraft team  
**Replaces:** `_extract_say_lines` / `_send_chat_chunks` / `MC_CHAT_FORMAT=say_lines`

---

## Decisions Made (User-Sign-Off)

| Decision | Value | Rationale |
|----------|-------|-----------|
| `MC_MAX_FRAGMENTS` | `3` | Test first. Can raise to 4–5 if Pamplinas monologues feel clipped. |
| Brevity guidance | Universal rule in `SOUL-base.md` | Applies to **all** modes (narrator, architect, companion, survivor, villager). Explicit: "keep your expression brief regardless of mode." |
| Anti-spam sliding window | **Per-bot** | Each bot tracks its own `recentFragments`. Simple, no cross-process coordination needed. |
| `<think>` tag stripping | **NOT in v1** | Current models don't emit them. Add only when a profile needs it. |
| Server-side chunking | **Yes** | Single source of truth. Python sends prose; server delivers fragments. |
| `SAY:` prefix | **Eliminated** | Unreliable. Model forgets it → silent message loss. |
| `MC_CHAT_FORMAT` env var | **Deprecated** | Stop reading it. Remove from `daemoncraft.py`. Document in release notes. |

---

## Philosophy

### P1. The LLM should not know about length limits

Asking the model to "use SAY: prefix" or "stay under 180 chars" is asking it to enforce a structural protocol concern in natural-language space. It will forget. When it does, the current pipeline silently drops everything — the worst-possible failure mode (no error, no fallback, divergent dashboard view).

**Rule:** length, fragmentation, and protocol limits are pipeline concerns. The model writes prose; the pipeline makes it fit.

The SOUL prompts give *stylistic* guidance ("keep chat conversational and brief — the player is in a game, not reading an essay") but never *structural* requirements. If the model produces 600 chars of beautiful prose, the pipeline ships it as 3 fragments. If it produces 6000 chars, the pipeline ships the first 3 fragments and appends `[...]`.

### P2. No delimiter system. Default-to-chat.

Two paths into Minecraft chat exist today:

1. **`mc_chat` tool call** — the agent explicitly emits a chat message via tool-use (already wired in `server.js:2256` and instructed in every SOUL profile).
2. **`final_response` auto-send** — the agent's natural-language response is sent as chat when triggered by player input (`MC_ALWAYS_CHAT` or chat-triggered turn).

Today, both paths converge on `b.chat()` raw, and the auto-send adds the `SAY:` filter on top. We collapse this:

**Decision:** keep both paths, but unify on a single chunk-and-send helper. Distinguish by *intent*:

- If the agent called `mc_chat` *during this turn* → it deliberately spoke. Send what it spoke. **Do NOT** also auto-send `final_response` (would duplicate).
- If the agent did *not* call `mc_chat` this turn → its `final_response` IS the chat output. Auto-send it.

This eliminates `SAY:` *and* eliminates the duplication risk that the current code awkwardly tolerates (`agent_loop.py:1003`).

### P3. The pipeline guarantees: at-least-some delivery

For every non-empty utterance the agent intends as chat, **at least the first fragment reaches Minecraft.** That is the load-bearing property. Additional fragments may be elided (per-turn cap, sliding-window throttle), but the floor is "the player sees something."

---

## Pipeline Design

### Concern Mapping

| Concern | Location | Why |
|---------|----------|-----|
| Decide what's "chat" vs tool calls / reasoning | `agent_loop.py` | Closest to LLM output and tool-call introspection |
| Chunk into ≤240-char fragments | `server.js` | Single source of truth; `mc_chat` tool path and HTTP path both hit it |
| Enforce 256-byte protocol ceiling | `server.js` | Minecraft protocol fact; closest to `b.chat()` |
| Per-call max-fragment cap (N=3) | `server.js` | Belongs with chunking |
| Sliding-window throttle (anti-spam) | `server.js` | Per-bot cross-call state |
| Inter-fragment cooldown (~300ms) | `server.js` | Already runs an event loop; keeps Python loop unblocked |
| Dashboard chat-log entries | `server.js` | One entry per fragment; both paths emit identically |
| Decide whether to auto-send `final_response` | `agent_loop.py` | Needs visibility into whether `mc_chat` tool was used this turn |

**Key consolidation:** `server.js` exports one function — `sendToMcChat(text, opts)` — and *both* the `mc_chat` tool action and the `/chat/send` HTTP endpoint route through it.

### B1. Agent output parsing (`agent_loop.py`)

Replace lines 79–137 (`_send_chat_chunks` + `_extract_say_lines`) with:

```python
import re

def _clean_response_for_chat(text: str) -> str:
    """Best-effort cleanup. Currently a no-op; reserved for future tag stripping."""
    if not text:
        return ""
    return text.strip()


def _post_chat(text: str) -> None:
    """Hand the full text to the bot server. Server does chunking + delivery.

    No pre-chunking, no length filtering, no SAY: parsing. The server is the
    sole authority on what reaches Minecraft.
    """
    text = _clean_response_for_chat(text)
    if not text:
        return
    payload = json.dumps({"message": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{MC_API_URL}/chat/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sent = data.get("fragments_sent", 0)
            dropped = data.get("fragments_dropped", 0)
            if dropped:
                print(f"[loop] Chat: {sent} fragments sent, {dropped} dropped (cap)", flush=True)
    except Exception as e:
        print(f"[loop] /chat/send failed: {e}", flush=True)
```

Replace the auto-send block at lines 1002–1018 with:

```python
elif response and (is_chat_triggered or os.getenv("MC_ALWAYS_CHAT", "").lower() in ("1", "true", "yes")):
    # If the agent used mc_chat this turn, it already spoke — don't duplicate.
    # Otherwise, the final_response IS the chat output.
    chat_msg = response.strip()
    if (
        chat_msg
        and not chat_msg.startswith("Operation interrupted")
        and not mc_chat_used
    ):
        _post_chat(chat_msg)
```

`mc_chat_used` is already computed at line 987 — we just gate on it instead of ignoring it.

### B2. Chunking algorithm (`server.js`)

```javascript
// Tunables (read once at startup from env, with defaults).
const MC_FRAGMENT_MAX_CHARS = parseInt(process.env.MC_FRAGMENT_MAX_CHARS || "240", 10);
const MC_MAX_FRAGMENTS = parseInt(process.env.MC_MAX_FRAGMENTS || "3", 10);
const MC_FRAGMENT_DELAY_MS = parseInt(process.env.MC_FRAGMENT_DELAY_MS || "300", 10);
const MC_PROTOCOL_BYTE_LIMIT = 256;        // Minecraft hard limit
const MC_THROTTLE_WINDOW_MS = 10_000;
const MC_THROTTLE_WINDOW_MAX = 5;

// Sliding-window state (per bot process — server.js is one bot = one process).
let recentFragments = [];

function chunkForMc(text, maxChars = MC_FRAGMENT_MAX_CHARS, maxFragments = MC_MAX_FRAGMENTS) {
  // 1. Normalize whitespace; collapse newlines into sentence terminators.
  text = text.replace(/\s+/g, ' ').trim();
  if (!text) return { fragments: [], truncated: false };

  // 2. Split on sentence boundaries (., !, ?, …) keeping the punctuation.
  const sentenceRe = /[^.!?…]+[.!?…]+(?:\s+|$)|[^.!?…]+$/g;
  const sentences = (text.match(sentenceRe) || [text]).map(s => s.trim()).filter(Boolean);

  // 3. Greedy packing: accumulate sentences into fragments while ≤ maxChars.
  const fragments = [];
  let buf = "";
  const flush = () => { if (buf) { fragments.push(buf); buf = ""; } };

  for (const s of sentences) {
    if (s.length > maxChars) {
      // Single sentence too long — flush current buf, then word-split this sentence.
      flush();
      fragments.push(...wordSplit(s, maxChars));
      continue;
    }
    const candidate = buf ? buf + ' ' + s : s;
    if (candidate.length <= maxChars) {
      buf = candidate;
    } else {
      flush();
      buf = s;
    }
  }
  flush();

  // 4. Cap fragment count. Append "[...]" to the last kept fragment if we drop tail.
  let truncated = false;
  if (fragments.length > maxFragments) {
    truncated = true;
    fragments.length = maxFragments;
    const last = fragments[maxFragments - 1];
    const ellipsis = " [...]";
    if (last.length + ellipsis.length <= maxChars) {
      fragments[maxFragments - 1] = last + ellipsis;
    } else {
      fragments[maxFragments - 1] = last.slice(0, maxChars - ellipsis.length).trimEnd() + ellipsis;
    }
  }

  // 5. Final byte-level safety: any fragment exceeding the protocol byte limit
  //    gets hard-cut. This should never trigger if maxChars=240 and content is
  //    mostly ASCII, but multi-byte characters (Spanish accents, emoji) can push
  //    a 240-char string over 256 bytes.
  return { fragments: fragments.map(byteCap), truncated };
}

function wordSplit(s, maxChars) {
  const out = [];
  let buf = "";
  for (const word of s.split(/\s+/)) {
    if (word.length > maxChars) {
      if (buf) { out.push(buf); buf = ""; }
      // Pathological: hard-cut a single long word.
      for (let i = 0; i < word.length; i += maxChars) out.push(word.slice(i, i + maxChars));
      continue;
    }
    const candidate = buf ? buf + ' ' + word : word;
    if (candidate.length <= maxChars) buf = candidate;
    else { out.push(buf); buf = word; }
  }
  if (buf) out.push(buf);
  return out;
}

function byteCap(s) {
  if (Buffer.byteLength(s, 'utf8') <= MC_PROTOCOL_BYTE_LIMIT) return s;
  let cut = s;
  while (Buffer.byteLength(cut, 'utf8') > MC_PROTOCOL_BYTE_LIMIT) cut = cut.slice(0, -1);
  return cut;
}
```

**Why sentence boundary first, word boundary second:** TTS-friendly chunks naturally end at sentence terminators. Word boundaries are the fallback for run-on prose. Hard cuts are reserved for adversarial/pathological inputs.

### B3. Unified delivery (`server.js`)

```javascript
async function sendToMcChat(text, { source = "auto" } = {}) {
  const { fragments, truncated } = chunkForMc(text);
  if (fragments.length === 0) {
    return { ok: true, fragments_sent: 0, fragments_dropped: 0, reason: "empty" };
  }

  // Sliding-window throttle (anti-runaway-loop) — PER BOT.
  const now = Date.now();
  recentFragments = recentFragments.filter(t => now - t < MC_THROTTLE_WINDOW_MS);
  let dropped = truncated ? 1 : 0;
  let sent = 0;

  for (const frag of fragments) {
    if (recentFragments.length >= MC_THROTTLE_WINDOW_MAX) {
      log(`[chat] Throttle: dropping fragment (${recentFragments.length}/${MC_THROTTLE_WINDOW_MAX} in window)`);
      dropped++;
      continue;
    }
    try {
      const b = ensureBot();
      b.chat(frag);
    } catch (e) {
      log(`[chat] b.chat() threw: ${e.message}`);
      dropped++;
      continue;
    }
    recentFragments.push(now);
    sent++;
    chatLog.push({ time: Date.now(), from: botName, message: frag, self: true });
    if (chatLog.length > MAX_LOG) chatLog.shift();
    broadcastDashboard('chat', chatLog.slice(-30));
    if (sent < fragments.length) await sleep(MC_FRAGMENT_DELAY_MS);
  }

  return { ok: true, fragments_sent: sent, fragments_dropped: dropped, truncated };
}
```

### B4. Wiring both paths

**`/chat/send` endpoint** (replaces `server.js:3447–3477`):

```javascript
if (path === '/chat/send') {
  const message = body?.message;
  const sender = body?.as;
  if (!message || typeof message !== 'string') {
    return respond(res, 400, { ok: false, error: "missing or invalid 'message'" });
  }
  if (message.length > 10_000) {
    return respond(res, 413, { ok: false, error: "message too large" });
  }

  // Server/tellraw special senders bypass chunking — they're commands, not chat.
  if (sender && sender.toLowerCase() !== botName.toLowerCase()) {
    return respond(res, 200, await sendAsSpecialSender(message, sender));
  }

  const result = await sendToMcChat(message, { source: "http" });
  return respond(res, 200, result);
}
```

**`mc_chat` tool action `chat`** (replaces `server.js:2256–2261`):

```javascript
async chat({ message }) {
  const result = await sendToMcChat(message, { source: "tool" });
  rememberSocialEvent({
    actor: getMyName(), kind: 'sent', channel: 'public',
    message,
    fragments: result.fragments_sent,
  });
  return {
    result: result.fragments_sent === 0
      ? `Message dropped (throttled or empty).`
      : `Sent: ${result.fragments_sent} fragment(s)${result.truncated ? ' [truncated]' : ''}`,
  };
}
```

**Whisper / chat_to** stay as-is for v1. They use `/msg` server commands, which carry their own length quirks. Chunking them properly is a follow-up; for v1 they keep their current behavior with one safety addition: if the resulting `/msg` line exceeds 256 bytes, hard-cut and log a warning.

### B5. Dashboard sync

Already nearly correct — once both paths funnel through `sendToMcChat`, every fragment lands in `chatLog` and is broadcast as `'chat'`. The dashboard chat panel will see exactly what Minecraft sees.

Separately, `log_agent_turn` still posts the *full raw response* to `/agent/log` for the dashboard's "agent activity" pane. That's fine and useful:

- **Chat pane** → fragments only, identical to MC.
- **Agent pane** → full raw response, tool calls, errors.

No change needed beyond clear labeling in the dashboard UI.

---

## C. SOUL Refactor — Moving Universal Rules to Base

`SOUL-base.md` currently has thin universal rules. Several concepts in `SOUL-rolemaster.md` are actually **universal** and should be promoted to the base layer so **all** casts benefit.

### C1. New rule: Brevity in Expression (All Modes)

**Add to `SOUL-base.md` immediately after the Language rule:**

```markdown
### 2. Brevity in Expression — All Modes, All Contexts

**Keep your expression brief regardless of mode.** Whether you are a narrator, architect, companion, or survivor, the player is in a game, not reading an essay. The chat pipeline can split long messages, but your default should be concise.

- **One thought per message.** If you have two distinct points, use two messages (or better: pick the more important one).
- **Avoid monologues.** Even in narrator or architect mode, brevity is respect for the player's attention.
- **Show, don't describe at length.** A single well-chosen detail is more powerful than a paragraph.
- **The pipeline handles the rest.** If a complex explanation is genuinely needed, write it — the system will split it into digestible fragments. But do not rely on this. Aim for 1–2 sentences by default.
```

This replaces the per-cast brevity rules:
- `SOUL-civilization.md` line 57: "Under 40 characters. One thought per message." → remove, now covered by base.
- `SOUL-landfolk.md` line 37: "Max 1 sentence. Never 2." → remove, now covered by base.
- `SOUL-rolemaster.md`: add nothing; the base rule now governs Pamplinas too.

### C2. Promote: Verify Before You Narrate

**Move from `SOUL-rolemaster.md` lines 339–349 to `SOUL-base.md`:**

```markdown
### 6. Verify Before You Narrate

**NEVER describe something you have not verified in the last 2 turns.** Your memory drifts. The world changes. Players break things.

Before mentioning any object, entity, or block in the world, verify it exists:
- `mc_perceive(type="scene")` — confirm blocks and entities are where you think
- `mc_perceive(type="nearby")` — confirm mobs are alive and present
- `mc_story(action="get_events", count=10)` — confirm your own past actions (spawns, placements, phase changes)

**If you spawned it and logged it, you may trust it.** If the player interacted with it, verify it.

**Example:** You spawned a husk at (205,70,205) and logged it. You may mention "the Guardian" without checking. But if the player says "I killed it," you MUST verify with `mc_perceive(type="nearby")` before declaring it dead.
```

### C3. Promote: State Is Truth

**Move from `SOUL-rolemaster.md` lines 383–396 to `SOUL-base.md`:**

```markdown
### 7. State Is Truth

Your memory is unreliable. The only truth is:
1. `story.json` (phases, flags, events, sensors) — if your cast uses it
2. Minecraft itself (blocks, entities, scoreboards)
3. Player chat (what they actually said)

**Before every narrative decision or world claim:**
```
mc_story(action="get_state")          — where are we?
mc_story(action="get_events", count=5) — what happened recently?
mc_perceive(type="scene")              — what exists right now?
```

Then decide. Then act. Then log.
```

### C4. Re-number existing base rules

Current base rules:
- 1. Language
- 2. Chat Relevance
- 3. Pre-Flight and Failure Recovery
- 4. Tool Use
- 5. Memory and Workspace
- 6. Safety

After insertion:
- 1. Language
- 2. **Brevity in Expression** (new)
- 3. Chat Relevance — Silence is Your Default
- 4. Pre-Flight and Failure Recovery
- 5. Tool Use
- 6. Memory and Workspace
- 7. **Verify Before You Narrate** (promoted from rolemaster)
- 8. **State Is Truth** (promoted from rolemaster)
- 9. Safety

### C5. Strip duplicates from cast SOULs

After promoting rules to base, remove equivalent sections from:
- `SOUL-civilization.md`: remove brevity lines (now base rule 2).
- `SOUL-landfolk.md`: remove "Max 1 sentence" (now base rule 2).
- `SOUL-rolemaster.md`: remove "Verify Before You Narrate" and "State Is Truth" sections (now base rules 7 and 8).

---

## D. Implementation Plan

### D1. Files changed

| File | Change |
|------|--------|
| `agents/bot/server.js` | Add `chunkForMc`, `wordSplit`, `byteCap`, `sendToMcChat`, per-bot sliding-window state. Rewire `/chat/send` and `mc_chat`'s `chat` action. |
| `agents/agent_loop.py` | Delete `_send_chat_chunks`, `_extract_say_lines`. Add `_clean_response_for_chat`, `_post_chat`. Replace auto-send block. Drop `MC_CHAT_FORMAT` branch. |
| `agents/daemoncraft.py` | Drop `env["MC_CHAT_FORMAT"] = chat_format` (line 432). Optionally surface new env vars. |
| `agents/SOUL-base.md` | Insert Brevity rule (2). Insert Verify Before You Narrate (7). Insert State Is Truth (8). Re-number. |
| `agents/SOUL-civilization.md` | Remove redundant brevity lines. |
| `agents/SOUL-landfolk.md` | Remove redundant "Max 1 sentence" rule. |
| `agents/SOUL-rolemaster.md` | Remove "Verify Before You Narrate" and "State Is Truth" sections. Keep mode-specific content. |

### D2. New env vars / config

| Var | Default | Purpose |
|-----|---------|---------|
| `MC_FRAGMENT_MAX_CHARS` | `240` | Per-fragment soft char cap |
| `MC_MAX_FRAGMENTS` | `3` | Per-call cap. Excess truncated with `[...]` |
| `MC_FRAGMENT_DELAY_MS` | `300` | Cooldown between consecutive fragments |
| `MC_THROTTLE_WINDOW_MS` | `10000` | Sliding window for anti-spam |
| `MC_THROTTLE_WINDOW_MAX` | `5` | Max fragments per window per bot |

**Removed:** `MC_CHAT_FORMAT`.

### D3. Migration path

Three deploys, each independently safe:

1. **PR #1 — server.js** — land chunking + unified delivery. Backward-compatible: old `agent_loop.py` still sends short lines, server passes them through unchanged.
2. **PR #2 — agent_loop.py + SOULs** — drop SAY: logic, add `_post_chat`. Promote universal rules to base SOUL, strip duplicates from casts.
3. **PR #3 — daemoncraft.py cleanup** — remove `MC_CHAT_FORMAT`. Surface new env vars if desired.

### D4. Verification

- **Smoke:** one bot, player says `Hello`. Expect 1 fragment, dashboard and MC match.
- **Long response:** prompt "tell me a long story". Expect 3 fragments, last with `[...]`.
- **Spam guard:** force 10 chat lines in 5s. Expect first 5, rest dropped.
- **Multi-byte:** Spanish/accents. Verify `byteCap` doesn't mangle.
- **mc_chat tool path:** force `mc_chat` with 600-char message. Expect chunking, no duplicate auto-send.
- **No tool, auto-send:** chat-triggered turn without `mc_chat`. Expect `final_response` chunked & delivered.

---

## E. What we explicitly are NOT doing (and why)

- **No queue-for-next-turn for dropped fragments.** Adds state, surprises players, couples turns. Truncate-with-`[...]` is honest and stateless.
- **No requiring a new delimiter** (e.g., `<chat>...</chat>`). Adds a new failure mode (model forgets the tag) for marginal benefit. `mc_chat_used` gating already disambiguates intentional vs. default chat.
- **No client-side chunking in `agent_loop.py`.** One source of truth (server). Python sends prose, server delivers fragments.
- **No per-character LLM penalties or system-prompt warnings.** The pipeline absorbs verbosity gracefully; the model is freed to focus on content.
- **No `chat_to`/`whisper` chunking in v1.** Documented as a follow-up.
- **No `<think>` tag stripping in v1.** Add when a model profile actually needs it.
