# Siqui Hermes Profile — Deployment Template (OAuth)

This directory contains the **authoritative** Hermes profile configuration for the Siqui agent.

## Installation

Copy these files to the live Hermes profile directory:

```bash
sudo -u siqui mkdir -p ~/.hermes/profiles/siqui
sudo -u siqui cp deploy/hermes/profiles/siqui/config.yaml ~/.hermes/profiles/siqui/config.yaml
sudo -u siqui cp deploy/hermes/profiles/siqui/.env       ~/.hermes/profiles/siqui/.env
```

> ⚠️ **IMPORTANT**: `daemoncraft.py` regenerates `config.yaml` on every start.
> The `.env` file is preserved across restarts.

## Authentication

This profile uses **Kimi CLI OAuth** (`kimi login`). No API key is required.
The OAuth token is read from `~/.kimi/credentials/kimi-code.json`.

## Endpoint

- **URL**: `https://api.kimi.com/coding/v1`
- **Model**: `kimi-for-coding`
- **Provider**: `kimi-coding`

## External changes tracked here

- `~/.hermes/profiles/siqui/config.yaml` — managed by daemoncraft.py
- `~/.hermes/profiles/siqui/.env` — managed by daemoncraft.py
- `~/.hermes/profiles/siqui/SOUL.md` — copy of `agents/prompts/rolemaster/siqui.md`
