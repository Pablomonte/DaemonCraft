# Server Setup

## Minecraft Forge Server with Phi-Craft

### Prerequisites

- Docker & Docker Compose
- CurseForge API key (for automatic modpack install) OR manual modpack download

### Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env and add your CF_API_KEY if using automatic install

# 2. Start the server
docker compose up -d minecraft

# 3. Check logs
docker compose logs -f minecraft
```

### Manual Modpack Fallback

If automatic download fails:

1. Download Phi-Craft server pack from CurseForge
2. Place it at `server/modpacks/phi-craft.zip`
3. Uncomment the manual fallback in `docker-compose.yml`
4. Run `docker compose up -d minecraft`

### Configuration

Key environment variables in `docker-compose.yml`:

| Variable | Value | Description |
|----------|-------|-------------|
| TYPE | FORGE | Server type |
| VERSION | 1.20.1 | Minecraft version |
| MEMORY | 12G | Max heap size |
| INIT_MEMORY | 8G | Initial heap size |
| ONLINE_MODE | false | Allow offline clients (for dev) |
| ALLOW_FLIGHT | true | Required for bot compatibility |

### Ports

- `25566` — Java Edition clients
- `19133` — Bedrock Edition clients (via GeyserMC)
