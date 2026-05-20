## FastAPI backend

Run the backend locally:

```powershell
python -m uvicorn app.api.main:app --reload
```

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
