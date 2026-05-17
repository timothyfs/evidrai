from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from evidrai.config import supabase_jwt_secret, supabase_url
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


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    url = supabase_url()
    if not url:
        raise AuthError("Server auth is not configured.", developer_detail="SUPABASE_URL is missing")
    return PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def _decode_with_jwks(token: str) -> dict[str, Any]:
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256", "RS256"],
        options={"verify_aud": False},
    )


def decode_supabase_access_token(token: str) -> dict[str, Any]:
    secret = supabase_jwt_secret()
    secret_error = ""
    try:
        if secret:
            try:
                return jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    options={"verify_aud": False},
                )
            except jwt.PyJWTError as exc:
                # Supabase projects can use asymmetric JWT signing. If a stale
                # SUPABASE_JWT_SECRET remains configured on Render, do not fail
                # closed before trying the project's JWKS endpoint.
                secret_error = str(exc)
                if not supabase_url():
                    raise
        return _decode_with_jwks(token)
    except AuthError:
        raise
    except jwt.PyJWTError as exc:
        detail = str(exc)
        if secret_error:
            detail = f"secret verification failed: {secret_error}; jwks verification failed: {detail}"
        raise AuthError("Invalid or expired authentication token.", developer_detail=detail)
    except Exception as exc:
        detail = str(exc)
        if secret_error:
            detail = f"secret verification failed: {secret_error}; jwks verification failed: {detail}"
        raise AuthError("Could not verify authentication token.", developer_detail=detail)


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
