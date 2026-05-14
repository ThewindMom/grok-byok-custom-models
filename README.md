# Grok BYOK custom models

Run the Grok CLI with your own OpenAI-compatible model provider instead of xAI-hosted inference.

This repository documents a working BYOK pattern for Grok CLI `0.1.210`:

- use Grok's custom model config
- point that model at a local proxy
- satisfy the CLI auth gate with a local dummy key
- forward inference to your provider key
- preserve interactive TUI streaming
- avoid the `ask_user_question` duplicate-tool panic in TUI mode

Tested with Fireworks AI + Kimi K2.6 Turbo, but the proxy is intentionally small and should work with most OpenAI-compatible `/chat/completions` providers after changing `GROK_BYOK_BASE_URL`, `GROK_BYOK_MODEL`, and the provider env key mapping.

## Important notes

This is a research/compatibility bridge. It does not patch the Grok binary and it does not provide xAI account access. You bring your own provider API key and pay that provider directly.

Do not commit real API keys. The examples use placeholders only.

## How it works

```text
Grok CLI
  -> custom model named byok
  -> http://127.0.0.1:8795/v1/chat/completions
  -> local proxy.py
  -> OpenAI-compatible provider, e.g. Fireworks
```

The proxy fixes request/response incompatibilities:

| Problem | Fix |
|---|---|
| Grok sends `grok-build` as model id in some paths | Rewrite it to `GROK_BYOK_MODEL` |
| Grok adds `model_id` to messages | Remove `model_id` before provider call |
| Grok tool schemas can contain `null` values | Strip `null` recursively from tool schemas |
| TUI needs streamed tokens | Forward SSE chunks line by line |
| Non-streaming headless calls need stable HTTP/1.1 | Send correct `Content-Length` |
| Grok 0.1.210 TUI/native ask-user can collide internally | Wrapper launches TUI with `--no-ask-user` |

## Quick start

### 1. Copy files

```bash
cp proxy.py ~/.grok/proxy.py
install -m 755 bin/grok-byok ~/.local/bin/grok-byok
```

### 2. Add custom model config

Append `examples/config.toml` to `~/.grok/config.toml`, or adapt it:

```toml
[model.byok]
model = "accounts/fireworks/routers/kimi-k2p6-turbo"
base_url = "http://127.0.0.1:8795"
name = "BYOK custom model"
env_key = "FIREWORKS_API_KEY"

[models]
default = "byok"
```

### 3. Export your provider key

```bash
export GROK_BYOK_API_KEY="<your-fireworks-api-key>"
export GROK_BYOK_BASE_URL="https://api.fireworks.ai/inference/v1"
export GROK_BYOK_MODEL="accounts/fireworks/routers/kimi-k2p6-turbo"
```

The wrapper maps `GROK_BYOK_API_KEY` to `FIREWORKS_API_KEY` because the example config uses `env_key = "FIREWORKS_API_KEY"`.

### 4. Run headless

```bash
grok-byok -p "Say hello in one sentence"
```

### 5. Run the TUI

```bash
grok-byok
```

If you see a welcome screen, start a new session from the TUI. The wrapper already passes `--no-ask-user` to avoid this Grok 0.1.210 panic:

```text
duplicate client_name "ask_user_question"
```

## Environment variables

| Variable | Default | Purpose |
|---|---:|---|
| `GROK_BYOK_API_KEY` | required | Your upstream provider API key |
| `GROK_BYOK_BASE_URL` | `https://api.fireworks.ai/inference/v1` | OpenAI-compatible API base URL |
| `GROK_BYOK_MODEL` | `accounts/fireworks/routers/kimi-k2p6-turbo` | Upstream model id |
| `GROK_BYOK_SOURCE_MODEL` | `grok-build` | Grok model id to rewrite |
| `GROK_BYOK_PORT` | `8795` | Local proxy port |
| `GROK_BYOK_PROXY` | `~/.grok/proxy.py` | Proxy path used by wrapper |
| `GROK_BYOK_PROXY_LOG` | `0` | Enable proxy debug logs |
| `GROK_BYOK_ENABLE_ASK_USER` | unset | Experimental: set to `1` to stop the wrapper adding `--no-ask-user` |
| `GROK_CODE_XAI_API_KEY` | `dummy-local-custom-model-key` | Dummy key satisfying Grok's auth gate |

## Provider notes

### Fireworks AI

Use:

```bash
export GROK_BYOK_BASE_URL="https://api.fireworks.ai/inference/v1"
export GROK_BYOK_MODEL="accounts/fireworks/routers/kimi-k2p6-turbo"
export GROK_BYOK_API_KEY="<your-fireworks-api-key>"
```

### Other OpenAI-compatible providers

Change:

```bash
export GROK_BYOK_BASE_URL="https://provider.example/v1"
export GROK_BYOK_MODEL="provider/model-name"
export GROK_BYOK_API_KEY="provider-key"
```

Then update `examples/config.toml` if the Grok config needs a different `env_key`. The wrapper currently exports `FIREWORKS_API_KEY` from `GROK_BYOK_API_KEY` because that was the tested path.

## Known limitations

- xAI-native features still require xAI services.
- Image/video generation with native Grok models is not covered.
- Tool calling depends on the upstream model following OpenAI tool-call JSON strictly.
- Native TUI ask-user is disabled by default because Grok CLI `0.1.210` can collide between the built-in model tool and the TUI extension method. See `docs/grok-0.1.210-notes.md`.
- `--tools` can break custom-model tool discovery in some Grok versions. Prefer default tools first.
- Fork/secondary models may still point at `grok-build` unless configured separately.

## Troubleshooting

### `duplicate client_name "ask_user_question"`

Use the wrapper, or launch TUI with:

```bash
grok -m byok --no-plan --no-ask-user
```

What this means: Grok CLI `0.1.210` contains both a model-facing GrokBuild tool implementation and a TUI/ACP extension method for the ask-user dialog. The collision happens in Grok's local tool/client registry, before the request reaches the proxy, so `proxy.py` cannot fix it. No config, plugin, MCP server, or marketplace cache entry is required to trigger it.

To retest native ask-user on a future Grok version:

```bash
GROK_BYOK_ENABLE_ASK_USER=1 grok-byok
```

### Proxy already running on port 8795

```bash
fuser -k 8795/tcp
```

Then rerun:

```bash
grok-byok -p "Say ok"
```

### Provider rejects schema

Enable logs:

```bash
export GROK_BYOK_PROXY_LOG=1
```

Then inspect:

```bash
tail -f ~/.grok/logs/byok-proxy-8795.err
```

### Headless works but TUI hangs

Confirm the proxy preserves streaming. This repository's `proxy.py` streams SSE chunks and only sends `Content-Length` for non-streaming responses.

## Repository structure

```text
.
├── bin/grok-byok           # wrapper around grok
├── proxy.py                # local OpenAI-compatible proxy
├── examples/config.toml    # Grok model config snippet
└── docs/architecture.md    # deeper explanation
```
