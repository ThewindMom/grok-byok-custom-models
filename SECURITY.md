# Security

Do not publish real API keys, auth files, session logs, or proxy logs.

This project intentionally uses a dummy `GROK_CODE_XAI_API_KEY` only to satisfy Grok CLI's local auth selection for custom-model execution. Real inference uses your BYOK provider key.

If you report an issue, redact:

- provider API keys
- prompts containing private code or data
- request/response logs
- `~/.grok/auth.json`
- session files under `~/.grok/sessions`
