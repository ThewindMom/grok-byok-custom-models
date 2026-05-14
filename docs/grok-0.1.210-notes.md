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

## Headless defaults

For headless single prompts, the wrapper adds `--always-approve` unless you pass your own `--permission-mode` or `--always-approve`.

## `--tools` caution

Some custom-model runs fail when a narrow `--tools` allowlist is used. Start with the default toolset and only restrict tools after the model/provider path is stable.
