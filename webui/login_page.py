from __future__ import annotations

from functools import cache
from pathlib import Path

from webui.config import WebUISettings

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@cache
def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def render_login_page(settings: WebUISettings) -> str:
    signup_panel = ""
    if settings.signup_enabled:
        signup_panel = _read_template("signup_panel.html").replace(
            "__MIN_PASSWORD_LENGTH__",
            str(settings.auth_min_password_length),
        )

    return (
        _read_template("login.html")
        .replace("__SIGNUP_PANEL__", signup_panel)
        .replace(
            "__MIN_PASSWORD_LENGTH__",
            str(settings.auth_min_password_length),
        )
    )
