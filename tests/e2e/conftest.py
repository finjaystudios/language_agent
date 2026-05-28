from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI_DIR = REPO_ROOT / "webui"
E2E_BASE_URL_ENV = "E2E_BASE_URL"
E2E_USERNAME = "e2e-user"
E2E_PASSWORD = "correct horse battery staple"
E2E_DISPLAY_NAME = "E2E User"
DEVICE_PRESETS = {
    "pixel": {"device": "Pixel 7", "label": "mobile-chrome"},
    "iphone": {"device": "iPhone 13", "label": "mobile-safari"},
    "tablet": {"device": "iPad Mini", "label": "tablet"},
}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(
    url: str,
    *,
    process: ManagedProcess | None = None,
    timeout_seconds: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process is not None:
            process.assert_running()
        try:
            response = requests.get(url, timeout=1)
            if response.status_code < 500:
                return
        except requests.RequestException as error:
            last_error = error
        time.sleep(0.25)
    detail = f"Timed out waiting for {url}: {last_error}"
    if process is not None:
        process.assert_running()
    raise RuntimeError(detail)


class ManagedProcess:
    def __init__(
        self,
        args: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        name: str,
    ) -> None:
        self.name = name
        self.stdout_path = Path(
            tempfile.mkstemp(prefix=f"{name}-", suffix=".out.log")[1]
        )
        self.stderr_path = Path(
            tempfile.mkstemp(prefix=f"{name}-", suffix=".err.log")[1]
        )
        self.stdout = self.stdout_path.open("w", encoding="utf-8")
        self.stderr = self.stderr_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdout=self.stdout,
            stderr=self.stderr,
            text=True,
        )

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.stdout.close()
        self.stderr.close()

    def assert_running(self) -> None:
        if self.process.poll() is not None:
            raise RuntimeError(
                f"{self.name} exited early with code {self.process.returncode}.\n"
                f"stdout: {self.stdout_path.read_text(encoding='utf-8', errors='replace')}\n"
                f"stderr: {self.stderr_path.read_text(encoding='utf-8', errors='replace')}"
            )


@pytest.fixture(scope="session")
def fake_backend() -> Iterator[str]:
    port = free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    process = ManagedProcess(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "fake_backend:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT / "tests" / "e2e",
        env=env,
        name="fake-backend",
    )
    try:
        wait_for_http(f"http://127.0.0.1:{port}/health", process=process)
        yield f"http://127.0.0.1:{port}"
    finally:
        process.stop()


@pytest.fixture(scope="session")
def external_chainlit_url() -> str | None:
    value = os.getenv(E2E_BASE_URL_ENV, "").strip()
    return value.rstrip("/") if value else None


@pytest.fixture(scope="session")
def chainlit_url(
    request: pytest.FixtureRequest, external_chainlit_url: str | None
) -> Iterator[str]:
    if external_chainlit_url:
        wait_for_http(external_chainlit_url)
        yield external_chainlit_url
        return

    fake_backend = request.getfixturevalue("fake_backend")
    port, process = start_chainlit(fake_backend, name="chainlit-webui")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        process.stop()


def start_chainlit(
    backend_url: str,
    *,
    name: str,
    api_key: str | None = "e2e-test-secret",
) -> tuple[int, ManagedProcess]:
    port = free_port()
    database_path = Path(tempfile.mkstemp(prefix=f"{name}-", suffix=".db")[1])
    initialize_e2e_database(database_path)
    env = os.environ.copy()
    env.update(
        {
            "AUTH_ENABLED": "true",
            "AUTH_MIN_PASSWORD_LENGTH": "12",
            "CHAINLIT_AUTH_SECRET": "e2e-chainlit-auth-secret",
            "CHAINLIT_HISTORY_ENABLED": "false",
            "DATABASE_SCHEME": "sqlite+aiosqlite",
            "DATABASE_HOST": "",
            "DATABASE_PORT": "0",
            "DATABASE_NAME": str(database_path),
            "DATABASE_USER": "",
            "DATABASE_PASSWORD": "",
            "DEBUG": "false",
            "FASTAPI_BASE_URL": backend_url,
            "REDIS_URL": "",
            "SESSION_COOKIE_SAMESITE": "lax",
            "SESSION_COOKIE_SECURE": "false",
            "SIGNUP_ENABLED": "true",
            "SIGNUP_REQUIRE_ADMIN_APPROVAL": "false",
            "WEBUI_REQUEST_TIMEOUT_SECONDS": "5",
            "WEBUI_STREAMING_ENABLED": "true",
        }
    )
    if api_key is None:
        env.pop("FASTAPI_API_KEY", None)
    else:
        env["FASTAPI_API_KEY"] = api_key
    process = ManagedProcess(
        [
            sys.executable,
            "-m",
            "chainlit",
            "run",
            "chainlit_app.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=WEBUI_DIR,
        env=env,
        name=name,
    )
    wait_for_http(f"http://127.0.0.1:{port}", process=process)
    return port, process


@contextmanager
def database_env(database_path: Path):
    previous_values = {key: os.environ.get(key) for key in _database_env(database_path)}
    for key, value in _database_env(database_path).items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _database_env(database_path: Path) -> dict[str, str]:
    return {
        "DATABASE_SCHEME": "sqlite+aiosqlite",
        "DATABASE_HOST": "",
        "DATABASE_PORT": "0",
        "DATABASE_NAME": str(database_path),
        "DATABASE_USER": "",
        "DATABASE_PASSWORD": "",
    }


def initialize_e2e_database(database_path: Path) -> None:
    with database_env(database_path):
        alembic_config = Config(str(REPO_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "head")
        _seed_test_user(database_path)


def _seed_test_user(database_path: Path) -> None:
    import asyncio

    from app.infrastructure.database.repositories import SQLAlchemyUserRepository
    from app.infrastructure.security.passwords import hash_password
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    async def seed() -> None:
        database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        repository = SQLAlchemyUserRepository(factory)
        existing_user = await repository.get_by_username(E2E_USERNAME)
        if existing_user is None:
            await repository.create_user(
                username=E2E_USERNAME,
                password_hash=hash_password(E2E_PASSWORD),
                display_name=E2E_DISPLAY_NAME,
                preferred_language="en",
                ui_theme="light",
            )
        await engine.dispose()

    asyncio.run(seed())


@pytest.fixture()
def chainlit_process_factory():
    processes: list[ManagedProcess] = []

    def start(
        backend_url: str,
        *,
        name: str = "chainlit-webui-test",
        api_key: str | None = "e2e-test-secret",
    ) -> str:
        port, process = start_chainlit(backend_url, name=name, api_key=api_key)
        processes.append(process)
        return f"http://127.0.0.1:{port}"

    yield start

    for process in processes:
        process.stop()


@pytest.fixture()
def requires_fake_backend(external_chainlit_url: str | None) -> None:
    if external_chainlit_url:
        pytest.skip(
            f"This test asserts fake-backend behavior; unset {E2E_BASE_URL_ENV} "
            "to run it against the deterministic fake backend."
        )


@pytest.fixture()
def requires_managed_chainlit(external_chainlit_url: str | None) -> None:
    if external_chainlit_url:
        pytest.skip(
            f"This test starts its own Chainlit process; unset {E2E_BASE_URL_ENV} "
            "to run it against the deterministic fake backend."
        )


@pytest.fixture()
def reset_fake_backend(fake_backend: str, external_chainlit_url: str | None) -> None:
    if external_chainlit_url:
        pytest.skip(
            f"This test asserts fake-backend requests; unset {E2E_BASE_URL_ENV} "
            "to run it against the deterministic fake backend."
        )
    requests.post(f"{fake_backend}/test/reset", timeout=2)


@pytest.fixture()
def backend_requests(fake_backend: str):
    def fetch() -> list[dict]:
        response = requests.get(f"{fake_backend}/test/requests", timeout=2)
        response.raise_for_status()
        return list(response.json()["requests"])

    return fetch


@pytest.fixture()
def unavailable_backend_url() -> str:
    return f"http://127.0.0.1:{free_port()}"


@pytest.fixture()
def emulated_page(browser, playwright, request):
    profile_name = getattr(request, "param", "pixel")
    if profile_name not in DEVICE_PRESETS:
        raise ValueError(f"Unknown device profile: {profile_name}")

    device_preset = DEVICE_PRESETS[profile_name]
    context = browser.new_context(**playwright.devices[device_preset["device"]])
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture()
def e2e_credentials() -> dict[str, str]:
    return {
        "username": E2E_USERNAME,
        "password": E2E_PASSWORD,
        "display_name": E2E_DISPLAY_NAME,
    }


def _login_to_chainlit(page, username: str, password: str) -> None:
    login_form = page.locator("#lla-login-form")
    username_input = login_form.locator('input[name="username"]')
    password_input = login_form.locator('input[name="password"]')
    username_input.wait_for(state="visible", timeout=15000)
    password_input.wait_for(state="visible", timeout=15000)
    username_input.fill(username)
    password_input.fill(password)
    login_form.get_by_role("button", name="Sign In").click()


@pytest.fixture()
def login_to_chainlit():
    return _login_to_chainlit


@pytest.fixture()
def chat_input():
    def find(page):
        return page.locator("textarea").first

    return find
