# Landfolk Mode

Landfolk Mode is the cooperative settlement experience of DaemonCraft: multiple persistent agents working together to build a village.

## Goal

Create a peaceful, collaborative multi-agent simulation where characters feel like genuine villagers with distinct skills and personalities.

## Ingredients
- One Mineflayer body per settler
- One Hermes profile per settler
- Shared peaceful goals (build, farm, explore)
- Character-specific skills and temperaments
- Cooperative chat and coordination
- Fair-play local perception

## Launch

```bash
python3 daemoncraft.py start landfolk
```

## What makes a good landfolk demo
- Characters have obvious complementary skills
- They coordinate on building projects
- They share resources and help each other
- Personality conflicts are mild and human
- The settlement visibly grows over time

## Current cast
- **Steve** — generalist / optimist
- **Moss** — farmer / quiet
- **Reed** — builder / meticulous
- **Flint** — miner / gruff but kind
- **Ember** — explorer / enthusiastic

## Management

```bash
python3 daemoncraft.py status landfolk   # check all settlers
python3 daemoncraft.py stop landfolk     # stop all settlers
python3 daemoncraft.py logs landfolk Reed  # tail logs
```
