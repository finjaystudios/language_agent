import importlib
import sys
import types


class FakeLlama:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def create_chat_completion(self, **kwargs):
        if kwargs.get("stream"):
            return iter([
                {"choices": [{"delta": {"content": "hel"}}]},
                {"choices": [{"delta": {}}]},
                {"choices": [{"delta": {"content": "lo"}}]},
            ])

        return {"choices": [{"message": {"content": "{\"response\": \"hello\"}"}}]}


def import_service_with_fake_llama(monkeypatch):
    fake_module = types.ModuleType("llama_cpp")
    fake_module.Llama = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)
    sys.modules.pop("llm.service", None)
    return importlib.import_module("llm.service")


def test_ask_llm_parses_structured_json_response(monkeypatch):
    service_module = import_service_with_fake_llama(monkeypatch)
    service = service_module.LLMService("model.gguf")

    result = service.ask_llm("system", "user", {"type": "object"})

    assert result == {"response": "hello"}


def test_stream_llm_yields_only_content_tokens(monkeypatch):
    service_module = import_service_with_fake_llama(monkeypatch)
    service = service_module.LLMService("model.gguf")

    result = list(service.stream_llm("system", "user"))

    assert result == ["hel", "lo"]
