# Cloud Model Router

PAO supports four workspace-scoped cloud providers: OpenAI, Anthropic, Google
Gemini and OpenRouter. Owners and admins manage them in **Settings &
Integrations → Cloud Models & Voice**.

Each provider card supports:

- entering or rotating an API key through a password field;
- server-side credential validation and live model discovery;
- selecting a model returned by that provider;
- a real minimal chat request to test the selected model;
- selecting one provider as the workspace default;
- disconnecting and deleting the encrypted credential.

Keys are encrypted with `INTEGRATION_ENCRYPTION_KEY` before storage in
`model_provider_connections`. Responses expose only the final four characters.
The browser never receives the stored key. Every connect, rotate, select,
default and disconnect operation requires owner/admin membership.

New PAO runs resolve the workspace default at execution time. The selected
gateway handles planning, specialist execution and the final response. Memory
fact extraction uses the same workspace provider; the current 768-dimensional
embedding store still uses local `embeddinggemma` until a separate embedding
migration is completed. If no cloud provider is selected, PAO continues to use
Ollama local.

Provider transport mapping:

| Provider | API |
| --- | --- |
| OpenAI | `/v1/models`, `/v1/chat/completions` |
| OpenRouter | `/api/v1/models`, `/api/v1/chat/completions` |
| Anthropic | `/v1/models`, `/v1/messages` |
| Google Gemini | `/v1beta/models`, `generateContent` / `streamGenerateContent` |

PAO does not silently copy environment API keys into the database. Existing
environment fields remain legacy/readiness signals; use the Settings page to
create a tested workspace connection.
