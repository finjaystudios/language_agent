import importlib
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def test_normal_runtime_imports_do_not_require_llama_cpp(monkeypatch):
    monkeypatch.delitem(sys.modules, "llama_cpp", raising=False)

    for module_name in (
        "app.interfaces.api.main",
        "app.application.agent_service",
        "app.worker.jobs",
        "app.infrastructure.llm.factory",
        "app.cli.main",
    ):
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)
