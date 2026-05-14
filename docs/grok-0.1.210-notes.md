# Grok 0.1.210 notes

This setup was tested against:

```text
grok 0.1.210 (8b63e9068)
```

## TUI `ask_user_question` panic

Observed panic:

```text
Agent Building failed, please check your config: ToolError("Requirements unsatisfied: [RequirementError { tool: \"GrokBuild:ask_user_question\", message: \"duplicate client_name \\\"ask_user_question\\\": already used by GrokBuild:ask_user_question. Use name_override to give each tool a unique client-facing name.\" ... }]")
```

Workaround:

```bash
grok -m byok --no-plan --no-ask-user
```

The wrapper applies this automatically for interactive TUI mode.

### Why it happens

This appears to be local Grok CLI behavior, not provider behavior and not a proxy bug.

Binary inspection of `grok 0.1.210 (8b63e9068)` shows two ask-user paths in the shipped executable:

- `crates/codegen/xai-grok-tools/src/implementations/grok_build/ask_user_question/...` — the model-facing GrokBuild tool implementation.
- `x.ai/ask_user_question` in `crates/codegen/xai-grok-shell/src/session/acp_session.rs` — the TUI/ACP extension method used to open the native question dialog.

The duplicate error is emitted by Grok's local registry while resolving client-facing tool names:

```text
duplicate client_name "ask_user_question": already used by GrokBuild:ask_user_question. Use name_override to give each tool a unique client-facing name.
```

That means the failure is before `/chat/completions`; `proxy.py` never sees it and cannot rewrite it away.

### What was ruled out

- `~/.grok/config.toml` does not need an explicit `ask_user_question` entry to hit this.
- `grok inspect` can show zero MCP servers, so MCP tool injection is not required.
- Marketplace/plugin cache entries are not the direct cause.
- Session state is not the root cause; the relevant tool and extension strings are hardcoded in the binary.
- `--tools` / `--disallowed-tools` are documented as headless-only in this version and are not a reliable TUI fix.

### Current status

There is no clean documented config-only way, in stable `0.1.210`, to keep the native TUI `ask_user_question` bridge enabled for this BYOK/custom-model path. The safe workaround is `--no-ask-user`, which leaves normal chat input working but removes the model-callable native question dialog.

`grok update --check` reports stable `0.1.210` as current. The alpha channel reported `0.1.211-alpha.2` available during testing, but this repository keeps the stable workaround because alpha may change behavior and can introduce unrelated regressions.

You can temporarily retest native ask-user on newer versions by setting:

```bash
GROK_BYOK_ENABLE_ASK_USER=1 grok-byok
```

If it still fails, unset that variable and use the default wrapper behavior.

### Binary patching

Binary patching is not recommended. The binary has both user-question tool schemas and ACP extension routing; changing strings risks breaking session UI, tool schema generation, or client/server protocol routing. Use `--no-ask-user` or test a newer Grok release instead.

## Headless defaults

For headless single prompts, the wrapper adds `--always-approve` unless you pass your own `--permission-mode` or `--always-approve`.

## `--tools` caution

Some custom-model runs fail when a narrow `--tools` allowlist is used. Start with the default toolset and only restrict tools after the model/provider path is stable.
