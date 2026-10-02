import secrets
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from observa.auth.dependencies import AuthenticatedUser, get_authenticated_user, require_roles
from observa.auth.security import hash_password, verify_password
from observa.database.database import SessionLocal
from observa.database.models import UserModel

router = APIRouter()
Role = Literal["admin", "operator", "executor"]


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    role: Role


class UserUpdateRequest(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None


def user_summary(user: UserModel) -> dict:
    return {
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def ensure_not_last_active_admin(session, user: UserModel, role: Optional[str], active: Optional[bool]):
    will_lose_admin = (
        user.role == "admin"
        and user.is_active
        and (role is not None and role != "admin" or active is False)
    )
    if not will_lose_admin:
        return

    active_admins = session.scalar(
        select(func.count()).select_from(UserModel).where(
            UserModel.role == "admin",
            UserModel.is_active.is_(True),
        )
    )
    if active_admins <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active admin cannot be demoted or deactivated",
        )


@router.get("/me")
def get_current_account(
    user: AuthenticatedUser = Depends(get_authenticated_user),
):
    return {
        "username": user.username,
        "role": user.role,
    }


@router.get("/users")
def list_users(_: AuthenticatedUser = Depends(require_roles("admin"))):
    with SessionLocal() as session:
        users = session.scalars(select(UserModel).order_by(UserModel.username)).all()
        return {"users": [user_summary(user) for user in users]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreateRequest,
    _: AuthenticatedUser = Depends(require_roles("admin")),
):
    username = request.username.strip().lower()
    initial_password = secrets.token_urlsafe(24)

    with SessionLocal() as session:
        existing_user = session.scalar(
            select(UserModel).where(UserModel.username == username)
        )
        if existing_user is not None:
            raise HTTPException(status_code=409, detail="Username already exists")

        user = UserModel(
            username=username,
            password_hash=hash_password(initial_password),
            role=request.role,
            is_active=True,
        )
        session.add(user)
        session.commit()

    return {
        "user": {"username": username, "role": request.role, "is_active": True},
        "initial_password": initial_password,
        "message": "Share this initial password securely. It is shown only once.",
    }


@router.patch("/users/{username}")
def update_user(
    username: str,
    request: UserUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    if request.role is None and request.is_active is None:
        raise HTTPException(status_code=422, detail="Provide a role or is_active change")

    with SessionLocal() as session:
        user = session.scalar(
            select(UserModel).where(UserModel.username == username.strip().lower())
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        ensure_not_last_active_admin(session, user, request.role, request.is_active)
        if user.id == current_user.id and user.role == "admin" and request.role not in (None, "admin"):
            raise HTTPException(status_code=409, detail="An admin cannot demote their own account")
        if user.id == current_user.id and user.role == "admin" and request.is_active is False:
            raise HTTPException(status_code=409, detail="An admin cannot deactivate their own account")

        if request.role is not None:
            user.role = request.role
        if request.is_active is not None:
            user.is_active = request.is_active
        session.commit()
        session.refresh(user)
        return {"user": user_summary(user)}


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    username: str,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    with SessionLocal() as session:
        user = session.scalar(
            select(UserModel).where(UserModel.username == username.strip().lower())
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if user.id == current_user.id:
            raise HTTPException(status_code=409, detail="An admin cannot delete their own account")

        ensure_not_last_active_admin(session, user, role="deleted", active=False)
        session.delete(user)
        session.commit()