from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import context as alembic_context
from alembic.config import Config

ROOT_DIR = Path(__file__).resolve().parents[1]


def load_module(module_name: str, file_path: Path) -> object:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_env_imports():
    original_config = getattr(alembic_context, "config", None)
    original_configure = getattr(alembic_context, "configure", None)
    original_begin_transaction = getattr(alembic_context, "begin_transaction", None)
    original_run_migrations = getattr(alembic_context, "run_migrations", None)
    original_is_offline_mode = getattr(alembic_context, "is_offline_mode", None)

    class DummyTransaction:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    alembic_context.config = Config(str(ROOT_DIR / "alembic.ini"))
    alembic_context.configure = lambda **_: None
    alembic_context.begin_transaction = lambda: DummyTransaction()
    alembic_context.run_migrations = lambda: None
    alembic_context.is_offline_mode = lambda: True

    module = load_module("test_alembic_env", ROOT_DIR / "alembic" / "env.py")

    try:
        assert hasattr(module, "run_migrations_offline")
        assert hasattr(module, "run_migrations_online")
    finally:
        if original_config is None:
            delattr(alembic_context, "config")
        else:
            alembic_context.config = original_config
        if original_configure is None:
            delattr(alembic_context, "configure")
        else:
            alembic_context.configure = original_configure
        if original_begin_transaction is None:
            delattr(alembic_context, "begin_transaction")
        else:
            alembic_context.begin_transaction = original_begin_transaction
        if original_run_migrations is None:
            delattr(alembic_context, "run_migrations")
        else:
            alembic_context.run_migrations = original_run_migrations
        if original_is_offline_mode is None:
            delattr(alembic_context, "is_offline_mode")
        else:
            alembic_context.is_offline_mode = original_is_offline_mode


def test_initial_migration_imports():
    module = load_module(
        "test_alembic_revision_20260528_0001",
        ROOT_DIR / "alembic" / "versions" / "20260528_0001_create_users_table.py",
    )

    assert module.revision == "20260528_0001"
    assert module.down_revision is None
