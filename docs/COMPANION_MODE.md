# Companion Mode

Companion Mode is the personal-scale experience of DaemonCraft: one embodied Hermes agent in your world.

## Goal

Make the agent feel like a real in-world friend, not a detached chatbot and not a benchmark bot.

## What matters most
- Responsiveness to player chat
- Helping with concrete gameplay tasks
- Remembering preferences and corrections
- Fair environment understanding
- Using vision (screenshots) when layout/build quality matters

## Good demo beats
- Player asks for a house and the agent surveys before building
- Agent remembers a prior preference (style, placement, caution)
- Natural back-and-forth chat while surviving together
- The agent uses `mc_screenshot` before making a spatial judgment

## Launch

```bash
python3 daemoncraft.py start companion
```

Or with a specific Minecraft server:

```bash
python3 daemoncraft.py start companion --mc-host 192.168.1.10 --mc-port 25565
```

## Good prompts
- build me a small starter house here
- follow me and keep me safe
- gather wood while I mine stone
- help me organize this base
- what do you think this area needs?

## Companion quality checklist
- Does it answer in chat quickly?
- Does it avoid blocking long tasks when the player is speaking?
- Does it build on the ground and verify layout?
- Does it admit uncertainty when it cannot see something?
- Does it feel like it is playing with the human, not just executing commands?
