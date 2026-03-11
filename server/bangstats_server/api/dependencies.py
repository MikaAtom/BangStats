from datetime import datetime, timezone

from fastapi import Header, HTTPException

from bangstats_server.core.db.models.user import User
from bangstats_server.core.db.repositories.token_repository import TokenRepository
from bangstats_server.core.services.user import UserService


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme")
    token_value = authorization[len(prefix) :].strip()
    if not token_value:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token_value


def get_current_user(authorization: str | None = Header(default=None)) -> User:
    token_value = _extract_bearer_token(authorization)
    with TokenRepository() as token_repo:
        token_repo.delete_expired(now=datetime.now(timezone.utc).replace(tzinfo=None))
        token = token_repo.get_by_value(token_value)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = UserService().get_user_by_id(token.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token user")
    return user


def assert_user_scope(requested_user_id: int, current_user: User) -> int:
    if int(requested_user_id) != int(current_user.id):
        raise HTTPException(status_code=403, detail="Forbidden for this user")
    return int(current_user.id)
