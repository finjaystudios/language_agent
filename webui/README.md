## Chainlit Web UI

This directory contains the separate Chainlit application for the Local Language
Agent Web UI. It is intentionally kept independent from the FastAPI backend
implementation and must communicate with the backend over HTTP.

Run from the repository root:

```powershell
pip install -r webui/requirements.txt
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

The current app provides a conversation scaffold with:

- a startup welcome message
- response mode settings for Auto, Translation, Definition, Learning, and General
- quick mode action buttons
- backend health status on chat start
- full-response requests to `POST /api/chat`
- streamed responses from `POST /api/chat/stream` for Translation and Learning
- readable backend connection and API errors

It does not import backend internals, call the LLM directly, or load a GGUF
model.

Configuration:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
```

Streaming is used only for modes currently supported by the backend streaming
contract: Translation and Learning. If the streaming request is rejected before
any chunks are displayed, the UI falls back to the full-response endpoint. If a
stream fails after partial output has already been shown, the UI displays a
readable error instead of retrying and risking a duplicated response.
