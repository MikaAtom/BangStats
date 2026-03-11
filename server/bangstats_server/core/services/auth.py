import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock

import bcrypt

from bangstats_server.core.db.models.user import User
from bangstats_server.core.db.repositories.token_repository import TokenRepository
from bangstats_server.core.services.user import UserService

TOKEN_TTL_DAYS = 30
RATE_LIMIT_WINDOW_MINUTES = 15
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_LOCKOUT_MINUTES = 15


class LoginRateLimiter:
    def __init__(self):
        self._lock = Lock()
        self._attempts: dict[str, list[datetime]] = {}
        self._locked_until: dict[str, datetime] = {}

    def _prune(self, key: str, now: datetime) -> None:
        window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
        self._attempts[key] = [stamp for stamp in self._attempts.get(key, []) if stamp >= window_start]
        if self._locked_until.get(key) and self._locked_until[key] <= now:
            self._locked_until.pop(key, None)

    def check_allowed(self, *, username: str, ip: str, now: datetime) -> bool:
        with self._lock:
            for key in (f"user:{username}", f"ip:{ip}"):
                self._prune(key, now)
                locked = self._locked_until.get(key)
                if locked and locked > now:
                    return False
            return True

    def register_failure(self, *, username: str, ip: str, now: datetime) -> None:
        with self._lock:
            for key in (f"user:{username}", f"ip:{ip}"):
                self._prune(key, now)
                attempts = self._attempts.setdefault(key, [])
                attempts.append(now)
                if len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
                    self._locked_until[key] = now + timedelta(minutes=RATE_LIMIT_LOCKOUT_MINUTES)

    def register_success(self, *, username: str, ip: str) -> None:
        with self._lock:
            self._attempts.pop(f"user:{username}", None)
            self._attempts.pop(f"ip:{ip}", None)
            self._locked_until.pop(f"user:{username}", None)
            self._locked_until.pop(f"ip:{ip}", None)


class AuthService:
    def __init__(self, rate_limiter: LoginRateLimiter):
        self._users = UserService()
        self._rate_limiter = rate_limiter

    @staticmethod
    def hash_password(raw_password: str) -> str:
        return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(raw_password: str, password_hash: str) -> bool:
        if not password_hash:
            return False
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False

    @staticmethod
    def _utc_now_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def issue_token(self, *, user_id: int) -> str:
        token_value = secrets.token_urlsafe(32)
        now = self._utc_now_naive()
        expires_at = now + timedelta(days=TOKEN_TTL_DAYS)
        with TokenRepository() as repo:
            repo.delete_expired(now=now)
            repo.create(token=token_value, user_id=user_id, expires_at=expires_at)
        return token_value

    def register(
        self,
        *,
        username: str,
        password: str,
        game_id: str,
        server: str,
    ) -> tuple[User, str]:
        if self._users.get_user_by_username(username):
            raise ValueError("username already exists")
        if self._users.get_user_by_game_id(game_id):
            raise ValueError("game_id already exists")

        user = self._users.create_user(
            {
                "username": username,
                "password_hash": self.hash_password(password),
                "game_id": game_id,
                "server": server,
            }
        )
        token = self.issue_token(user_id=int(user.id))
        return user, token

    def login(self, *, username: str, password: str, ip: str) -> tuple[User, str]:
        now = self._utc_now_naive()
        if not self._rate_limiter.check_allowed(username=username, ip=ip, now=now):
            raise RuntimeError("rate_limited")

        user = self._users.get_user_by_username(username)
        if not user or not self.verify_password(password, user.password_hash):
            self._rate_limiter.register_failure(username=username, ip=ip, now=now)
            raise ValueError("Invalid username or password")

        self._rate_limiter.register_success(username=username, ip=ip)
        token = self.issue_token(user_id=int(user.id))
        return user, token

    @staticmethod
    def logout(token_value: str) -> None:
        with TokenRepository() as repo:
            repo.delete_by_value(token_value)
