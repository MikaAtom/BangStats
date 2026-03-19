from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from bangstats_server.api.dependencies import _extract_bearer_token
from bangstats_server.api.schemas.auth import (
    AuthResponse,
    LegacyLoginRequest,
    LegacyPasswordSetupRequest,
    LoginRequest,
    RegisterRequest,
)
from bangstats_server.api.schemas.users import UserResponse
from bangstats_server.core.services.auth import AuthService, LoginRateLimiter

router = APIRouter()
rate_limiter = LoginRateLimiter()
auth_service = None


def _get_auth_service() -> AuthService:
    if auth_service is not None:
        return auth_service
    return AuthService(rate_limiter=rate_limiter)


def _to_user_response(user) -> UserResponse:
    payload = jsonable_encoder(user)
    if payload.get("role") is None:
        payload["role"] = "user"
    if payload.get("excluded_song_ids") is None:
        payload["excluded_song_ids"] = []
    return UserResponse(**payload)


@router.post("/auth/register", response_model=AuthResponse)
def register(data: RegisterRequest):
    auth_service = _get_auth_service()
    try:
        user, token = auth_service.register(
            username=data.username.strip(),
            password=data.password,
            game_id=data.game_id.strip(),
            server=data.server,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthResponse(token=token, user=_to_user_response(user))


@router.post("/auth/login", response_model=AuthResponse)
def login(data: LoginRequest, request: Request):
    auth_service = _get_auth_service()
    ip = request.client.host if request.client else "unknown"
    try:
        user, token = auth_service.login(
            username=data.username.strip(),
            password=data.password,
            ip=ip,
        )
    except RuntimeError as exc:
        if str(exc) == "rate_limited":
            raise HTTPException(status_code=429, detail="Too many login attempts") from exc
        if str(exc) == "password_setup_required":
            raise HTTPException(
                status_code=403,
                detail="Account requires password setup. Use legacy password setup with your game ID.",
            ) from exc
        raise
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return AuthResponse(token=token, user=_to_user_response(user))


@router.post("/auth/legacy-password-setup", response_model=AuthResponse)
def legacy_password_setup(data: LegacyPasswordSetupRequest):
    auth_service = _get_auth_service()
    try:
        user, token = auth_service.activate_legacy_account(
            username=data.username.strip(),
            game_id=data.game_id.strip(),
            password=data.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthResponse(token=token, user=_to_user_response(user))


@router.post("/auth/legacy-login", response_model=AuthResponse)
def legacy_login(data: LegacyLoginRequest, request: Request):
    auth_service = _get_auth_service()
    ip = request.client.host if request.client else "unknown"
    try:
        user, token = auth_service.login_legacy(
            username=data.username.strip(),
            game_id=data.game_id.strip(),
            ip=ip,
        )
    except RuntimeError as exc:
        if str(exc) == "rate_limited":
            raise HTTPException(status_code=429, detail="Too many login attempts") from exc
        raise
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return AuthResponse(token=token, user=_to_user_response(user))


@router.post("/auth/logout")
def logout(request: Request):
    auth_service = _get_auth_service()
    token_value = _extract_bearer_token(request.headers.get("Authorization"))
    auth_service.logout(token_value)
    return {"status": "ok"}
