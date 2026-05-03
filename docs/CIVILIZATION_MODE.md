# Civilization Mode

Civilization Mode is the world-scale experience of DaemonCraft: multiple persistent Hermes agents in the same Minecraft world.

## Goal

Show that the same system used for a personal companion can scale into a readable multi-agent social simulation.

## Ingredients
- One Mineflayer body per character
- One Hermes profile per character
- One memory store per character
- Character-specific prompt / social agenda
- Public chat + direct messages + overhearing
- Fair-play local perception instead of shared omniscience

## Launch

```bash
python3 daemoncraft.py start civilization
```

The launcher aborts if bot bodies fail to connect, instead of wasting agent launches on disconnected characters.

## What makes a good civilization demo
- Distinct personalities are obvious quickly
- Public and private communication both matter
- There is one catalyst event (danger, shortage, secret, request, vote)
- One or two social consequences become visible
- Logs / overlays make the dynamics legible

## Suggested catalyst events
- Public request to build shelter before night
- One private whisper about food shortage
- Accusation of theft or hoarding
- Disagreement about where to settle
- Human player publicly praises one agent and privately instructs another

## Current cast
- **Marcus** — leader / control drive
- **Sarah** — caretaker / wants space
- **Jin** — knowledge hoarder
- **Dave** — approval-seeking talker
- **Lisa** — scout / distrustful
- **Tommy** — thief / loner
- **Elena** — crisis authority

## Management

```bash
python3 daemoncraft.py status civilization   # check all agents
python3 daemoncraft.py stop civilization     # stop all agents
python3 daemoncraft.py logs civilization Marcus  # tail logs
```
