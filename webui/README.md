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

The initial app only displays a welcome message and a placeholder response. It
does not import backend internals, call the LLM directly, or load a GGUF model.
