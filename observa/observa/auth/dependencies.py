from dataclasses import dataclass
from typing import Callable, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from observa.auth.security import decode_access_token
from observa.database.database import SessionLocal
from observa.database.models import UserModel

bearer_scheme = HTTPBearer(auto_error=False)
VALID_ROLES = {"admin", "operator", "executor"}


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    role: str


def get_authenticated_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        claims = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthorized

    username = claims.get("sub")
    if not isinstance(username, str) or not username:
        raise unauthorized

    with SessionLocal() as session:
        user = session.scalar(select(UserModel).where(UserModel.username == username))
        if user is None or not user.is_active or user.role not in VALID_ROLES:
            raise unauthorized
        principal = AuthenticatedUser(
            id=user.id,
            username=user.username,
            role=user.role,
        )
    return principal


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(user: AuthenticatedUser = Depends(get_authenticated_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency