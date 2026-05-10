# DaemonCraft Documentation

Last updated: 2026-05-10

## Core Docs

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture, flow diagrams, services, data flows, key decisions |
| [OPERATIONS.md](OPERATIONS.md) | How to start/stop/restart, health checks, troubleshooting, logs |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Golden rules, repo structure, how to make changes, provider config, SOUL composition |

## Reference Docs

| Document | What it covers |
|---|---|
| [GEMMA_ANDY_AUDIT.md](GEMMA_ANDY_AUDIT.md) | Mariano's design vs our implementation, idiom guide, gaps |
| [../MEMORY.md](../MEMORY.md) | Project memory: agent state, stability fixes, known pitfalls, decisions |

## Quick Reference

### Start everything
```bash
systemctl --user start daemoncraft.service daemoncraft-cast.service embodied-service.service
```

### Full update (code changes)
```bash
cd ~/Projects/DaemonCraft
PYTHONPATH=~/Projects/DaemonCraft:$PYTHONPATH python3 agents/daemoncraft.py update companion
```

### Health
```bash
curl -s http://localhost:3001/health  # Steve
curl -s http://localhost:3002/health  # gAndy
curl -s http://localhost:7790/health  # Embodied
```

### Dashboards
- Steve: http://localhost:3001/dashboard
- gAndy: http://localhost:3002/dashboard
