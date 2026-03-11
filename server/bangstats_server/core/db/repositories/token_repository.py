from datetime import datetime
from typing import Optional

from sqlmodel import delete, select

from bangstats_server.core.db import get_session
from bangstats_server.core.db.models.token import Token


class TokenRepository:
    def __init__(self):
        self._session_gen = get_session()
        self._session = next(self._session_gen)

    def close(self):
        self._session_gen.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create(self, *, token: str, user_id: int, expires_at: datetime) -> Token:
        item = Token(token=token, user_id=user_id, expires_at=expires_at)
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return item

    def get_by_value(self, token_value: str) -> Optional[Token]:
        statement = select(Token).where(Token.token == token_value)
        return self._session.exec(statement).first()

    def delete_by_value(self, token_value: str) -> bool:
        statement = delete(Token).where(Token.token == token_value)
        result = self._session.exec(statement)
        self._session.commit()
        return bool(result.rowcount)

    def delete_expired(self, *, now: datetime) -> int:
        statement = delete(Token).where(Token.expires_at <= now)
        result = self._session.exec(statement)
        self._session.commit()
        return int(result.rowcount or 0)
