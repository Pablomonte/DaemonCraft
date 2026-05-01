# Siqui Hermes Profile — Deployment Template

This directory contains the **authoritative** Hermes profile configuration for the Siqui agent.

## Installation

Copy these files to the live Hermes profile directory:

```bash
sudo -u siqui mkdir -p ~/.hermes/profiles/siqui
sudo -u siqui cp deploy/hermes/profiles/siqui/config.yaml ~/.hermes/profiles/siqui/config.yaml
sudo -u siqui cp deploy/hermes/profiles/siqui/.env       ~/.hermes/profiles/siqui/.env
```

> ⚠️ **IMPORTANT**: `daemoncraft.py` regenerates `config.yaml` on every start, but
> now writes `base_url` under `model:` **as well as** under `providers:` so Hermes
> honours the Moonshot endpoint. The `.env` file is preserved across restarts.

## Required API Key

The Kimi Coding OAuth token (from `kimi login`) only works on `api.kimi.com/coding/v1`,
and that endpoint **rejects** `kimi-k2.6` with:

> "Kimi For Coding is currently only available for Coding Agents such as Kimi CLI..."

To use `kimi-k2.6` you need a **Moonshot API key** (`sk-...`):

1. Go to https://platform.moonshot.ai/ and create an API key.
2. Add it to `~/.hermes/profiles/siqui/.env`:
   ```bash
   KIMI_API_KEY=sk-your-key-here
   ```
3. Restart the service:
   ```bash
   sudo systemctl restart daemoncraft-siqui.service
   ```

`agent_loop.py` now loads the profile `.env` and passes the key to `AIAgent`,
preventing Hermes from falling back to the OAuth-based `kimi-coding` router that
hard-codes `api.kimi.com/coding/v1`.

## External changes tracked here

- `~/.hermes/profiles/siqui/config.yaml` — created 2026-05-01 20:01
- `~/.hermes/profiles/siqui/.env` — created 2026-05-01 20:01
- `~/.hermes/profiles/siqui/SOUL.md` — updated 2026-05-01 20:01
