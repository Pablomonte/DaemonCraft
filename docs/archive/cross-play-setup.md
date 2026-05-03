# Cross-Play Setup

## Overview

DaemonCraft supports both Java Edition (PC) and Bedrock Edition (mobile, console, Windows 10) clients.

## Architecture

```
Bedrock Client (Phone/Console)
       |
       | UDP 19132
       v
+-------------+      TCP 25565      +-------------+
|   Geyser    |  ---------------->  |   Minecraft |
| Standalone  |   Minecraft         | Forge Server|
|             |   Protocol          | (Phi-Craft) |
+-------------+                     +-------------+
       ^                                    ^
       |                                    |
+-------------+                      +-------------+
|  Bedrock    |                      |   Java      |
|  Auth       |                      |   Client    |
|  (Offline)  |                      |   (Offline) |
+-------------+                      +-------------+
```

## Geyser Standalone

We use Geyser Standalone (not the Forge mod) because:
1. Geyser-Forge is community-maintained and less stable
2. No official Floodgate-Forge exists
3. Standalone provides clean separation of concerns

## Configuration

### Geyser Config

Located at `server/geyser/config.yml`:

- **Bedrock port**: 19132 (UDP + TCP)
- **Remote server**: `minecraft:25565` (Docker service name)
- **Auth type**: `offline` (allows Bedrock players without Microsoft accounts)

### Why Not Floodgate?

Floodgate is not available for Forge servers. It exists for:
- BungeeCord/Velocity proxies
- Spigot/Paper servers
- Fabric servers

For Phase 0, we use Geyser's `offline` auth mode which achieves the same goal: Bedrock players can join without Microsoft accounts.

## Connecting

### Java Edition
- Address: `localhost:25566`
- No account needed (online-mode=false)

### Bedrock Edition
- Address: `localhost:19133`
- Server port: 19133
- No Microsoft account needed
- Username can be any name

## Docker Compose

```bash
# Geyser starts automatically with the server
docker compose up -d

# View Geyser logs
docker compose logs -f geyser
```

## Troubleshooting

### Bedrock can't see the server
- Ensure UDP port 19132 is forwarded/open
- Check firewall settings
- Verify Geyser is running: `docker compose ps`

### Authentication errors
- Geyser config must use `auth-type: offline` for our dev setup
- Ensure Minecraft server has `online-mode=false`

### Connection refused
- Ensure Minecraft server is fully started (Geyser waits for it)
- Check `docker compose logs minecraft` for startup errors
