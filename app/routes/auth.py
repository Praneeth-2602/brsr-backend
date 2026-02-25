from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from ..services import users_service

router = APIRouter(tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
async def signup(payload: SignupRequest):
    try:
        user = await users_service.create_user(payload.email, payload.password, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    token = users_service.create_access_token({"sub": str(user["_id"]), "role": user.get("role", "user")})
    return {"access_token": token, "token_type": "bearer", "user": {"id": str(user["_id"]), "email": user["email"], "name": user.get("name")}}


@router.post("/login")
async def login(payload: LoginRequest):
    user = await users_service.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = users_service.create_access_token({"sub": str(user["_id"]), "role": user.get("role", "user")})
    return {"access_token": token, "token_type": "bearer", "user": {"id": str(user["_id"]), "email": user["email"], "name": user.get("name")}}
