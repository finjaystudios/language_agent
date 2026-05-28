from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user_profile import UsernameAlreadyExistsError, UserProfile
from app.infrastructure.database.models import UserModel, utc_now


class SQLAlchemyUserRepository:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_username(self, username: str) -> UserProfile | None:
        async with self._session_factory() as session:
            user = await session.scalar(
                select(UserModel).where(UserModel.username == username)
            )
            return user.to_domain() if user else None

    async def get_by_id(self, user_id: int) -> UserProfile | None:
        async with self._session_factory() as session:
            user = await session.get(UserModel, user_id)
            return user.to_domain() if user else None

    async def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        display_name: str | None = None,
        role: str = "user",
        is_active: bool = True,
        is_admin: bool = False,
        preferred_language: str | None = None,
        ui_theme: str | None = None,
        profile_metadata: dict[str, object] | None = None,
    ) -> UserProfile:
        async with self._session_factory() as session:
            user = UserModel(
                username=username,
                display_name=display_name,
                password_hash=password_hash,
                role=role,
                is_active=is_active,
                is_admin=is_admin,
                preferred_language=preferred_language,
                ui_theme=ui_theme,
                profile_metadata=dict(profile_metadata or {}),
            )
            session.add(user)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise UsernameAlreadyExistsError(username) from error
            await session.refresh(user)
            return user.to_domain()

    async def update_last_login(self, user_id: int) -> UserProfile | None:
        async with self._session_factory() as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                return None

            now = utc_now()
            user.last_login_at = now
            user.updated_at = now
            await session.commit()
            await session.refresh(user)
            return user.to_domain()

    async def list_users(self) -> list[UserProfile]:
        async with self._session_factory() as session:
            users = await session.scalars(
                select(UserModel).order_by(UserModel.username.asc())
            )
            return [user.to_domain() for user in users.all()]
