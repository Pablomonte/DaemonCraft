# Siqui Hermes Profile — Deployment Template

This directory contains the **authoritative** Hermes profile configuration for the Siqui agent.

## Installation

Copy these files to the live Hermes profile directory:

```bash
sudo -u siqui mkdir -p ~/.hermes/profiles/siqui
sudo -u siqui cp deploy/hermes/profiles/siqui/config.yaml ~/.hermes/profiles/siqui/config.yaml
sudo -u siqui cp deploy/hermes/profiles/siqui/.env       ~/.hermes/profiles/siqui/.env
```

> ⚠️ **IMPORTANT**: `daemoncraft.py` regenerates this profile on every start.  
> The fix in `daemoncraft.py` (commit after `53922de`) now writes `base_url` under
> `model:` **as well as** under `providers:`, so Hermes actually honours the
> Moonshot endpoint instead of falling back to the hard-coded `api.kimi.com/coding/v1`.

## Why this matters

Hermes reads the API endpoint from `model.base_url` (not `providers.*.base_url`).
Without `model.base_url`, the `kimi-coding` provider hard-codes
`https://api.kimi.com/coding/v1`, which returns **HTTP 403** for Moonshot keys.

## External changes tracked here

- `~/.hermes/profiles/siqui/config.yaml` — created 2026-05-01 20:01 by manual edit
- `~/.hermes/profiles/siqui/.env` — created 2026-05-01 20:01 with `MC_API_URL`
- `~/.hermes/profiles/siqui/SOUL.md` — updated 2026-05-01 20:01 (copy of `agents/prompts/rolemaster/siqui.md`)
