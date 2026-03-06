from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder

from bangstats_server.api.schemas.users import UserCreate, UserResponse, UserUpdate
from bangstats_server.core.services.user import UserService

router = APIRouter()
user_service = UserService()


def _to_user_response(user) -> UserResponse:
    payload = jsonable_encoder(user)
    return UserResponse(**payload)


@router.get("/users", response_model=UserResponse)
def get_user_by_username(username: str = Query(..., min_length=1)):
    user = user_service.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_user_response(user)


@router.post("/users", response_model=UserResponse)
def create_user(data: UserCreate):
    try:
        user = user_service.create_user(data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_user_response(user)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int):
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_user_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, data: UserUpdate):
    try:
        user = user_service.update_user(
            user_id,
            data.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return _to_user_response(user)
