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
- placeholder assistant responses showing the planned HTTP payload shape
- an error display placeholder for the later backend client

It does not import backend internals, call the LLM directly, or load a GGUF
model.
