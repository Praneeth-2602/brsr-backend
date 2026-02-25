from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext

from ..config import get_settings
from ..database import get_db
from ..models import PyObjectId

_settings = get_settings()
_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def _verify_password(password: str, hashed: str) -> bool:
    return _pwd_ctx.verify(password, hashed)


async def get_user_by_email(email: str) -> Optional[dict]:
    db = get_db()
    return await db["users"].find_one({"email": email})


async def get_user_by_id(user_id: str) -> Optional[dict]:
    db = get_db()
    return await db["users"].find_one({"_id": PyObjectId(user_id)})


async def create_user(email: str, password: str, name: Optional[str] = None) -> dict:
    db = get_db()
    existing = await db["users"].find_one({"email": email})
    if existing:
        raise ValueError("User already exists")
    hashed = _hash_password(password)
    now = datetime.utcnow()
    user = {"email": email, "hashed_password": hashed, "name": name or "", "created_at": now, "role": "user"}
    result = await db["users"].insert_one(user)
    user["_id"] = result.inserted_id
    return user


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    secret = _settings.local_jwt_secret
    if not secret:
        raise RuntimeError("Local JWT secret not configured")
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=(expires_minutes or _settings.local_jwt_exp_minutes))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, secret, algorithm=_settings.local_jwt_algorithm)
    return token


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not _verify_password(password, user.get("hashed_password", "")):
        return None
    return user
