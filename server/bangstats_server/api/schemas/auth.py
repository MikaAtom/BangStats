from typing import Literal

from pydantic import BaseModel, Field

from bangstats_server.api.schemas.users import UserResponse


ServerCode = Literal["en", "jp", "tw", "cn", "kr"]


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    game_id: str = Field(min_length=1)
    server: ServerCode = "en"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LegacyPasswordSetupRequest(BaseModel):
    username: str = Field(min_length=1)
    game_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LegacyLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    game_id: str = Field(min_length=1)


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
