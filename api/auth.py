"""Auth0 JWT verification for FastAPI using JWKS (RS256)."""
import os
import requests
from jose import jwt, JWTError
from jose.constants import ALGORITHMS
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_ISSUER = os.getenv("AUTH0_ISSUER") or f"https://{AUTH0_DOMAIN}/"
JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"

_jwks = None


class VerifiedUser(BaseModel):
    auth0_id: str
    email: str | None = None
    roles: list[str] = []


def _get_jwks() -> dict:
    global _jwks
    if _jwks is None:
        resp = requests.get(JWKS_URL, timeout=10)
        resp.raise_for_status()
        _jwks = resp.json()
    return _jwks


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> VerifiedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    token = credentials.credentials

    try:
        jwks = _get_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[ALGORITHMS.RS256],
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER,
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )

    email = payload.get("email")
    if email is None:
        email = payload.get(f"{AUTH0_ISSUER}email", None)

    return VerifiedUser(
        auth0_id=payload["sub"],
        email=email,
        roles=payload.get(
            f"{AUTH0_ISSUER}roles",
            payload.get("roles", []),
        ),
    )
