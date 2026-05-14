# Architecture

## Goal

Use Grok CLI as intended — same binary, same TUI, same session machinery — while routing model inference to a user-owned OpenAI-compatible provider key.

## Components

### Grok CLI

Grok supports custom models in `~/.grok/config.toml`. The important settings are:

```toml
[model.byok]
model = "accounts/fireworks/routers/kimi-k2p6-turbo"
base_url = "http://127.0.0.1:8795"
env_key = "FIREWORKS_API_KEY"
```

The CLI still performs an auth-method check. For custom model usage, a dummy `GROK_CODE_XAI_API_KEY` is enough to satisfy that local gate while inference is sent to the configured custom model endpoint.

### Local proxy

The proxy exists because Grok's request format is close to OpenAI-compatible, but not always accepted by third-party providers.

Request mutations:

1. Replace `grok-build` with `GROK_BYOK_MODEL`.
2. Remove `model_id` from messages.
3. Remove `null` entries from tool schemas.
4. Pass all other headers/body fields through.

Response behavior:

1. If request/response is streaming, forward chunks immediately.
2. If non-streaming, buffer and send exact `Content-Length`.
3. Close the connection explicitly for HTTP/1.1 stability.

### Wrapper

`bin/grok-byok` handles the ergonomics:

1. Requires `GROK_BYOK_API_KEY`.
2. Exports dummy `GROK_CODE_XAI_API_KEY`.
3. Starts the proxy if needed.
4. Runs `grok -m byok --no-plan`.
5. Adds `--always-approve` for headless prompts unless the caller chose a permission mode.
6. Adds `--no-ask-user` for TUI mode to avoid the Grok 0.1.210 native ask-user registry collision.

## Why not call the provider directly from Grok?

Grok's custom model setting does call the configured base URL, but several compatibility details break common providers:

- model id mismatch in some tool/session paths
- extra message fields
- nullable schema values
- streaming headers/chunking in the TUI

The proxy keeps those fixes local and auditable.

## Security model

- Your real provider key stays in your shell environment.
- The dummy xAI key is not a real credential.
- The proxy only binds to `127.0.0.1`.
- No request/response logging is enabled by default.
- If you enable logging, assume prompts and tool schemas may appear in logs.

## Tested baseline

- Grok CLI: `0.1.210`
- OS: Linux x86_64
- Provider: Fireworks AI
- Model: `accounts/fireworks/routers/kimi-k2p6-turbo`
- Headless: working
- TUI startup: working with `--no-ask-user`
- SSE streaming: working through proxy

## Native ask-user limitation

Grok CLI `0.1.210` ships both:

- a GrokBuild `ask_user_question` tool implementation for model tool calls
- an `x.ai/ask_user_question` TUI/ACP extension method for opening the native question dialog

In the BYOK/custom-model TUI path these can collide in Grok's local client-facing tool registry. Because this happens before inference, the proxy cannot fix it. The wrapper disables the native bridge by default with `--no-ask-user`. Set `GROK_BYOK_ENABLE_ASK_USER=1` only when testing a Grok version where the collision may be fixed.
