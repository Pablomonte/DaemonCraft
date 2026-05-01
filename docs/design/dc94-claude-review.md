# DC-94 Gateway Adapter — Review por Claude Code (Claude Opus 4)

## Q1 — Coexistencia correctness

La partición es arquitectónicamente sana. El env var se lee por turno (`os.getenv` dentro del loop), lo cual está bien — el environment se setea al lanzar el proceso, no hay problema de atomicidad. No hay race condition: el loop y el gateway son procesos separados consumiendo el mismo WS stream independientemente.

**Gap**: si el loop está en medio de una LLM call cuando el gateway también recibe el mismo mensaje, ambos llaman a la AI independientemente. La respuesta del loop se suprime por el env var, pero la LLM call igual corre y gasta tokens. Para MVP está bien, pero hay que trackearlo.

## Q2 — Session mapping y `group_sessions_per_user`

**Esto está roto por default.** `build_source` lee `group_sessions_per_user` de `self.config.extra` con default **`True`**. Con el default, cada jugador en un world channel obtiene su propia sesión aislada keyed por `(world_name, player)`. El agent nunca ve el contexto compartido.

**Fix**: agregar `"group_sessions_per_user": False` al default extra en la config factory.

## Q3 — WebSocket reconnect

5s fijo está bien para MVP. Para producción, exponencial backoff con cap y jitter (1s → 2s → 4s → 8s → 30s max) reduce thundering herd si el bot API restartea. Dejar flat por ahora, crear ticket follow-up.

## Q4 — TTS flow

Comportamiento actual: audio URL va a dashboards, el texto completo va por `send()` que **clampa a 500 chars**. Recomendación: enviar el **texto completo** a chat cuando es un TTS transcript, ya que el audio lleva el contenido completo y el texto es fallback para jugadores sin audio.

Minor: el emoji `🗣️` no renderiza en Minecraft vanilla chat (sale como `?`). Usar `"[Voice message]"` plano.

## Q5 — `/chat/send` backwards compatibility

Limpio. `target` solo se chequea con truthy guard, así que callers antiguos que omiten `target` caen en el path existente de `sendToMcChat`. ✓

## Q6 — UUID vs username: **critical double-auth bug**

El adapter hace su propio auth check en `_handle_chat_entry` (UUID o username). Luego llama `handle_message()`, que eventualmente llama al gateway `_is_user_authorized()`, que re-chequea `DAEMONCRAFT_ALLOWED_USERS` contra `source.user_id` — pero `user_id` está seteado a `from_` (el **username**).

Si `DAEMONCRAFT_ALLOWED_USERS` contiene solo UUIDs (el identificador estable recomendado):
- Adapter check: pasa (UUID match) ✓
- Gateway re-check: `source.user_id == from_` (username, no UUID) → **falla** ✗
- Resultado: cada jugador autorizado es silenciosamente rechazado

**Fix**: usar UUID como `user_id` en `SessionSource` cuando está disponible:

```python
source = self.build_source(
    chat_id=chat_id,
    chat_name=chat_id,
    chat_type=chat_type,
    user_id=sender_uuid or from_,   # ← era: from_
    user_name=from_,
    thread_id=thread_id,
)
```

## Q7 — Missing integration points

Ninguno es blocker para e2e básico. El path MVP (player chat → gateway → AIAgent → HTTP POST /chat/send) está completo sin cron, tool routing, wizard, o channel directory.

## Q8 — Code quality issues en `daemoncraft.py`

**`send()` `is_group` metadata dependency**: El método lee `is_group` de `metadata`. No está claro que el gateway runner popule `is_group` en metadata para DaemonCraft. Si no lo hace, todos los sends defaultearán a whisper (`payload["whisper"] = True`), rompiendo broadcast replies.

Approach más robusto: mantener un `_world_names: set[str]` que se popule a medida que llegan mensajes broadcast, y chequear `chat_id in self._world_names` para decidir broadcast vs whisper.

**`_ws_session` reuse**: usar la WS session para HTTP POSTs está bien con aiohttp, pero considerar renombrar a `_http_session` o `_session` para reducir confusión.

**Type annotation**: `set[str]` (PEP 585) requiere Python 3.9+. Si el gateway targetea 3.8, usar `Set[str]` de `typing`.

**`/msg` vs `/tell`** en `server.js`: ambos funcionan en vanilla, pero `/tell` es más canónico. Considerar usar `/tell` siempre para mensajes dirigidos.

## Summary

| Issue | Severidad | Fix requerido? |
|-------|-----------|----------------|
| UUID/username double-auth bug (Q6) | **High** | Sí — antes del e2e con UUID allowlist |
| `group_sessions_per_user` default True (Q2) | **Medium** | Sí — set False en extra o documentar |
| `send()` `is_group` metadata fragility (Q8) | **Medium** | Sí — verificar o reemplazar con `_world_names` set |
| `is_group` local var unused | Low | Cleanup |
| Emoji en TTS fallback | Low | Cosmetic |
| WS reconnect backoff | Low | Post-MVP |
| TTS text clamping | Low | Aceptable por ahora |
