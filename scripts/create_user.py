from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a local LanguageAgent user profile."
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name")
    parser.add_argument("--admin", action="store_true")
    parser.add_argument("--inactive", action="store_true")
    parser.add_argument("--role", default="user")
    parser.add_argument("--preferred-language")
    parser.add_argument("--ui-theme")
    return parser


async def run() -> int:
    from app.domain.user_profile import UsernameAlreadyExistsError
    from app.infrastructure.database.repositories import SQLAlchemyUserRepository
    from app.infrastructure.database.session import get_async_session_factory
    from app.infrastructure.security.passwords import hash_password

    args = build_parser().parse_args()
    repository = SQLAlchemyUserRepository(get_async_session_factory())

    try:
        created = await repository.create_user(
            username=args.username,
            password_hash=hash_password(args.password),
            display_name=args.display_name,
            role=args.role,
            is_active=not args.inactive,
            is_admin=args.admin,
            preferred_language=args.preferred_language,
            ui_theme=args.ui_theme,
        )
    except UsernameAlreadyExistsError:
        print(
            f"Refusing to create duplicate username: {args.username}",
            file=sys.stderr,
        )
        return 1

    print(
        "Created user "
        f"username={created.username} id={created.id} "
        f"admin={created.is_admin} active={created.is_active}"
    )
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
