from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt

from evidrai.config import supabase_jwt_secret
from evidrai.errors import EvidraiError


class AuthError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: str = "") -> None:
        super().__init__(message, code="auth_error", status_code=401, developer_detail=developer_detail)


@dataclass(frozen=True)
class AuthContext:
    owner_id: str = ""
    auth_method: str = "anonymous"
    email: str = ""

    @property
    def authenticated(self) -> bool:
        return self.auth_method == "supabase_jwt" and bool(self.owner_id)


def decode_supabase_access_token(token: str) -> dict[str, Any]:
    secret = supabase_jwt_secret()
    if not secret:
        raise AuthError("Server auth is not configured.", developer_detail="SUPABASE_JWT_SECRET is missing")
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired authentication token.", developer_detail=str(exc))


def context_from_headers(*, authorization: str = "", owner_header: str = "") -> AuthContext:
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        claims = decode_supabase_access_token(token)
        owner_id = str(claims.get("sub") or "").strip()
        if not owner_id:
            raise AuthError("Authentication token is missing a subject.")
        return AuthContext(owner_id=owner_id, auth_method="supabase_jwt", email=str(claims.get("email") or ""))

    owner_id = (owner_header or "").strip()
    return AuthContext(owner_id=owner_id, auth_method="anonymous_header" if owner_id else "anonymous")
