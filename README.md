## FastAPI backend

Run the backend locally:

```powershell
python -m uvicorn app.api.main:app --reload
```

OpenAPI docs are available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

### Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Lightweight health check. Does not initialise the LLM. |
| `GET` | `/` | Service metadata. |
| `POST` | `/api/chat` | Full response chat endpoint. |
| `POST` | `/api/chat/stream` | Server-Sent Events streaming chat endpoint. |

### Full response request

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Define recursion in simple terms","mode":"definition"}'
```

Example response shape:

```json
{
  "mode": "definition",
  "response": "...",
  "intent": {
    "mode": "definition",
    "confidence": "high",
    "should_switch_mode": true,
    "reason": "Mode supplied by API request.",
    "clarification_question": ""
  },
  "data": {},
  "metadata": {
    "session_id": null
  }
}
```

### Streaming request

Stream a chat response with Server-Sent Events:

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Translate this sentence to isiXhosa: Good morning","mode":"translation"}'
```

Streaming responses use `text/event-stream` events such as:

```text
data: {"mode": "translation", "token": "..."}

data: {"mode": "translation", "done": true}
```

### Error response shape

Errors use a stable JSON shape and do not include stack traces:

```json
{
  "error": "validation_error",
  "message": "Request validation failed.",
  "details": {
    "errors": []
  }
}
```

Expected status codes:

- `400`: invalid client input such as an unsupported streaming mode.
- `422`: request body schema validation failures such as a missing or empty message.
- `500`: LLM initialisation/runtime failures or unexpected internal errors.

### Known limitations

- The backend uses the same local GGUF model and GPU prerequisites as the CLI.
- Chat endpoints initialise the local model lazily on first use.
- Streaming is currently supported for modes configured as streaming in the existing agent (`translation` and `learning`).
- If an LLM failure occurs after an SSE response has started, the API emits a sanitized SSE error event instead of changing the HTTP status code.

## Bruno API client

Git-tracked Bruno collections live in `bruno/local-language-agent-api`.

Open that folder in Bruno and select the `Local` environment, or run it with the
Bruno CLI:

```powershell
bru run bruno/local-language-agent-api --env Local
```
