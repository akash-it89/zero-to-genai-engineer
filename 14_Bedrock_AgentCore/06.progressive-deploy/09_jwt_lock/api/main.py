"""Step 09 — Cognito JWT lock on /api/me. Chat arrives in step 10."""
from __future__ import annotations

import os
from typing import Any

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

app = FastAPI(title="Lauki Support API", version="0.9.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_bearer = HTTPBearer(auto_error=False)
_jwks_client: PyJWKClient | None = None


def _auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED", "").lower() in {"1", "true", "yes"}


def _cognito_configured() -> bool:
    return bool(
        (os.getenv("COGNITO_USER_POOL_ID") or "").strip()
        and (os.getenv("COGNITO_CLIENT_ID") or "").strip()
    )


def _region() -> str:
    return os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION") or "us-east-1"


def _issuer() -> str:
    pool = os.environ["COGNITO_USER_POOL_ID"].strip()
    return f"https://cognito-idp.{_region()}.amazonaws.com/{pool}"


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{_issuer()}/.well-known/jwks.json")
    return _jwks_client


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    if _auth_disabled() or not _cognito_configured():
        return {"sub": "local-dev", "cognito:username": "local-dev"}
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Login required")
    token = creds.credentials
    client_id = os.environ["COGNITO_CLIENT_ID"].strip()
    try:
        key = _jwks().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=_issuer(),
            options={"require": ["exp", "iss", "sub"], "verify_aud": False},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
    if claims.get("token_use") == "id" and claims.get("aud") != client_id:
        raise HTTPException(status_code=401, detail="Token audience mismatch")
    return claims


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "auth": "disabled" if _auth_disabled() or not _cognito_configured() else "cognito",
        "step": 9,
    }


@app.get("/api/me")
def me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    return {
        "sub": user.get("sub"),
        "username": user.get("cognito:username") or user.get("username") or user.get("sub"),
    }
