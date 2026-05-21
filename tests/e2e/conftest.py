from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBUI_DIR = REPO_ROOT / "webui"


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
def chainlit_url(fake_backend: str) -> Iterator[str]:
    port, process = start_chainlit(fake_backend, name="chainlit-webui")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        process.stop()


def start_chainlit(backend_url: str, *, name: str) -> tuple[int, ManagedProcess]:
    port = free_port()
    env = os.environ.copy()
    env.update(
        {
            "DEBUG": "false",
            "FASTAPI_BASE_URL": backend_url,
            "WEBUI_REQUEST_TIMEOUT_SECONDS": "5",
            "WEBUI_STREAMING_ENABLED": "true",
        }
    )
    process = ManagedProcess(
        [
            sys.executable,
            "-m",
            "chainlit",
            "run",
            "app.py",
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


@pytest.fixture()
def chainlit_process_factory():
    processes: list[ManagedProcess] = []

    def start(backend_url: str, *, name: str = "chainlit-webui-test") -> str:
        port, process = start_chainlit(backend_url, name=name)
        processes.append(process)
        return f"http://127.0.0.1:{port}"

    yield start

    for process in processes:
        process.stop()


@pytest.fixture()
def reset_fake_backend(fake_backend: str) -> None:
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
