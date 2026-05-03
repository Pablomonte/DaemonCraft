# Mod Integration Plan

## Key Phi-Craft Mods

### ComputerCraft: Tweaked

- In-game computers with Lua scripting
- Turtles for automated resource gathering
- HTTP API for external communication
- **Integration**: Bot can read computer output, send Lua scripts, coordinate turtle swarms

### Create

- Mechanical contraptions and kinetic energy
- Automated farms, processing lines, transport
- Redstone link wireless control
- **Integration**: Bot monitors contraption status, triggers mechanical systems via redstone

### Industrial Mods (Mekanism, Thermal Series)

- Ore processing, power generation, storage
- Pipes, ducts, cables for logistics
- Machines with configurable modes
- **Integration**: Bot reads machine GUIs (via block entities), automates ore pipelines

### Exploration Dimensions

- If present: Twilight Forest, The Undergarden, etc.
- **Integration**: Bot navigation and mapping in non-overworld dimensions

## API Extension Points

Planned endpoints for mod-aware commands:

```
POST /command
{
  "command": "computercraft_run",
  "params": {
    "computer_id": 1,
    "script": "turtle.dig()"
  }
}
```

```
POST /command
{
  "command": "create_monitor",
  "params": {
    "contraption_name": "wheat_farm",
    "metric": "rpm"
  }
}
```
