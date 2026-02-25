from functools import lru_cache
from typing import Any, Dict

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

security = HTTPBearer()
_settings = get_settings()


@lru_cache
def _jwks() -> Dict[str, Any]:
    url = f"{_settings.SUPABASE_URL}/auth/v1/keys"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    token = credentials.credentials

    # Try Supabase JWKS (RS256)
    try:
        jwks = _jwks()
        unverified_header = jwt.get_unverified_header(token)
        key = next(k for k in jwks["keys"] if k["kid"] == unverified_header.get("kid"))
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=_settings.SUPABASE_JWT_AUD if getattr(_settings, "SUPABASE_JWT_AUD", None) else None,
            options={"verify_exp": True},
        )
    except Exception:
        # Fallback to local HS256 tokens if configured
        if _settings.local_jwt_secret:
            try:
                payload = jwt.decode(
                    token,
                    _settings.local_jwt_secret,
                    algorithms=[_settings.local_jwt_algorithm],
                    options={"verify_exp": True},
                )
            except Exception:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication")
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication")

    user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user identifier")

    role = payload.get("role") or (payload.get("app_metadata") or {}).get("role") or "user"

    # Provide both `user_id` and `sub` for compatibility with existing code
    return {"user_id": user_id, "sub": user_id, "role": role, "raw": payload}
