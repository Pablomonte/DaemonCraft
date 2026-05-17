# Local Agent Setup — Give an Existing Hermes Agent a Minecraft Body

This guide is for giving an **already-existing Hermes agent** (one that lives in `~/.hermes/`, not an isolated `~/agents/<name>/` workspace) a Minecraft body through DaemonCraft.

**Use case:** Ani has a Hermes agent in her `~/.hermes/`. Oliva wants to give that same agent a Minecraft body without creating a second identity or isolated workspace.

---

## What You Need Before Starting

1. **Hermes agent profile already exists** in `~/.hermes/` with `config.yaml`, `.env`, etc.
2. **DaemonCraft repo cloned** and `daemoncraft-cast.service` installed (`systemctl --user status daemoncraft-cast.service` should show it exists).
3. **Node.js bot dependencies installed** in `~/Projects/DaemonCraft/agents/bot/` (`npm install` or `pnpm install`).
4. **Minecraft server running** and reachable.

---

## Step 1: Create the Cast YAML

Create `~/Projects/DaemonCraft/agents/casts/<cast-name>.yaml`:

```yaml
cast:
  name: lab
  mode: direct
  agents:
    - name: CompAII
      type: local           # <-- key: reuses existing Hermes profile
      profile: compaii      # existing profile name in ~/.hermes/
      bot:
        config: config-compaii.json
        api_port: 3003
      agent_loop: true      # optional: spawn heartbeat loop for debugging
      toolsets:
        - minecraft
        - embodiment
```

Set it as the active cast:

```bash
mkdir -p ~/.config/daemoncraft
echo "CAST=lab" > ~/.config/daemoncraft/cast.conf
```

---

## Step 2: Create the Bot Config (Body)

Create `~/Projects/DaemonCraft/agents/bot/config-<name>.json`:

```json
{
  "minecraft": {
    "host": "localhost",
    "port": 25565,
    "username": "CompAII",
    "auth": "offline"
  },
  "server": {
    "api_port": 3003
  },
  "chat": {
    "fragment_max_chars": 240,
    "max_fragments": 3,
    "fragment_delay_ms": 300
  }
}
```

Make sure `username` matches the name you want the bot to have in Minecraft, and `api_port` matches the cast YAML.

---

## Step 3: Configure Hermes Environment

Add to `~/.hermes/.env`:

```bash
MC_API_URL=http://localhost:3003
MC_USERNAME=CompAII
EMBODIED_SERVICE_URL=http://localhost:7790
```

Enable the DaemonCraft platform in `~/.hermes/config.yaml`:

```yaml
platforms:
  daemoncraft:
    enabled: true
    extra:
      bot_api_url: http://localhost:3003
      bot_username: CompAII

platform_toolsets:
  daemoncraft:
    - minecraft      # <-- required for mc_* tools
    - embodiment     # optional
    - messaging
    - memory
    - vision
    - tts
```

---

## Step 4: Symlink the Minecraft Toolset

Instead of copying `minecraft_tools.py`, symlink it so changes in the repo reflect immediately:

```bash
ln -s ~/Projects/DaemonCraft/agents/hermescraft/minecraft_tools.py \
  ~/.hermes/hermes-agent/tools/daemoncraft_minecraft.py
```

Verify discovery:

```bash
cd ~/.hermes/hermes-agent && python3 -c "
from tools.registry import discover_builtin_tools, registry
discover_builtin_tools()
print(sorted(registry.get_registered_toolset_names()))
"
```

You should see `daemoncraft_minecraft` or `minecraft` in the list.

---

## Step 5: Start the Cast

```bash
systemctl --user restart daemoncraft-cast.service
systemctl --user status daemoncraft-cast.service
```

This starts:
- The Mineflayer bot process (`node server.js --config config-<name>.json`)
- Optionally, the `agent_loop.py` heartbeat if `agent_loop: true`

---

## Step 6: Verify

Check the bot is online:

```bash
curl -s http://localhost:3003/status | python3 -m json.tool
```

You should see `ok: true`, position, health, etc.

Test a tool from a Hermes CLI session:

```bash
hermes chat -q "use mc_bit to scan around you"
```

Or directly:

```bash
curl -s "http://localhost:3003/blocks?x1=560&x2=570&y1=119&y2=121&z1=-422&z2=-412&format=binary"
```

---

## Key Differences from Cast Agents (Steve, gAndy)

| Aspect | Cast Agent (Steve) | Local Agent (CompAII) |
|--------|-------------------|----------------------|
| Workspace | `~/agents/<name>/` created | Reuses `~/.hermes/` |
| Gateway | `hermes-gateway@<name>.service` | Default `hermes-gateway.service` or CLI |
| Venv | Isolated `~/agents/<name>/venv/` | Deploy-target `~/.hermes/hermes-agent/venv/` |
| Memory | Isolated HMK | Shared `~/.hermes/agent-memory/` |
| `agent_loop` | Always spawned | Optional (`true`/`false`) |

---

## Troubleshooting

- **Bot not connecting:** Check `MC_API_URL` is correct and the bot server is listening on the right port (`lsof -i :3003`).
- **Tools missing:** Verify `platform_toolsets.daemoncraft` includes `minecraft` (not just `embodiment`).
- **mc_bit errors:** Make sure `MC_API_URL` is set **before** the Hermes session starts. Changing `.env` mid-session has no effect on already-loaded modules.
- **Stale gateway:** If switching from a cast agent to a local agent, stop old per-agent gateways (`systemctl --user stop hermes-gateway@steve`) to avoid port conflicts.

---

## Next Steps

- Read `~/Projects/DaemonCraft/agents/SOUL-lab.md` for the lab agent behavior template.
- Read `~/.hermes/SOUL_daemoncraft.md` for CompAII's runtime embodiment rules.
- Backport any universal improvements from `SOUL-lab.md` to `agents/SOUL-base.md`.
