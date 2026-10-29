from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from observa.auth.dependencies import AuthenticatedUser, get_authenticated_user, require_roles
from observa.auth.security import (
    generate_strong_password,
    hash_password,
    normalize_email,
    password_policy_errors,
)
from observa.database.database import SessionLocal
from observa.database.models import UserModel
from observa.security import audit

router = APIRouter()
Role = Literal["admin", "operator", "executor"]


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    email: str = Field(min_length=6, max_length=254)
    role: Role

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        return normalize_email(email)


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$",
    )
    email: Optional[str] = Field(default=None, min_length=6, max_length=254)
    role: Optional[Role] = None
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: Optional[str]) -> Optional[str]:
        if email is None:
            return None
        return normalize_email(email)


class UserPasswordUpdateRequest(BaseModel):
    password: str


def user_summary(user: UserModel) -> dict:
    return {
        "username": user.username,
        "email": user.email,
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
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    username = request.username.strip().lower()
    email = request.email.strip().lower()
    initial_password = generate_strong_password()

    with SessionLocal() as session:
        existing_user = session.scalar(
            select(UserModel).where(
                (UserModel.username == username) | (UserModel.email == email)
            )
        )
        if existing_user is not None:
            raise HTTPException(status_code=409, detail="Username or email already exists")

        user = UserModel(
            username=username,
            email=email,
            password_hash=hash_password(initial_password),
            role=request.role,
            is_active=True,
        )
        session.add(user)
        try:
            session.flush()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Username or email already exists",
            ) from error
        audit.record_security_event(
            action="user.create",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="user",
            resource_id=str(user.id),
            request=http_request,
            session=session,
        )
        session.commit()

    return {
        "user": {
            "username": username,
            "email": email,
            "role": request.role,
            "is_active": True,
        },
        "initial_password": initial_password,
        "message": "Share this initial password securely. It is shown only once.",
    }


@router.patch("/users/{username}")
def update_user(
    username: str,
    request: UserUpdateRequest,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    if (
        request.username is None
        and request.email is None
        and request.role is None
        and request.is_active is None
    ):
        raise HTTPException(
            status_code=422,
            detail="Provide a username, email, role, or is_active change",
        )

    with SessionLocal() as session:
        user = session.scalar(
            select(UserModel).where(UserModel.username == username.strip().lower())
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        updated_username = request.username.strip().lower() if request.username else None
        updated_email = request.email.strip().lower() if request.email else None
        username_changed = updated_username is not None and updated_username != user.username
        email_changed = updated_email is not None and updated_email != user.email
        if username_changed or email_changed:
            uniqueness_conditions = []
            if username_changed:
                uniqueness_conditions.append(UserModel.username == updated_username)
            if email_changed:
                uniqueness_conditions.append(UserModel.email == updated_email)
            existing_user = session.scalar(
                select(UserModel).where(
                    UserModel.id != user.id,
                    or_(*uniqueness_conditions),
                )
            )
            if existing_user is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Username or email already exists",
                )

        ensure_not_last_active_admin(session, user, request.role, request.is_active)
        if user.id == current_user.id and user.role == "admin" and request.role not in (None, "admin"):
            raise HTTPException(status_code=409, detail="An admin cannot demote their own account")
        if user.id == current_user.id and user.role == "admin" and request.is_active is False:
            raise HTTPException(status_code=409, detail="An admin cannot deactivate their own account")

        if updated_username is not None:
            user.username = updated_username
        if updated_email is not None:
            user.email = updated_email
        if request.role is not None:
            user.role = request.role
        if request.is_active is not None:
            user.is_active = request.is_active
        audit.record_security_event(
            action="user.update",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="user",
            resource_id=str(user.id),
            request=http_request,
            session=session,
        )
        try:
            session.commit()
        except IntegrityError as error:
            session.rollback()
            if username_changed or email_changed:
                raise HTTPException(
                    status_code=409,
                    detail="Username or email already exists",
                ) from error
            raise
        session.refresh(user)
        return {"user": user_summary(user)}


@router.patch("/users/{username}/password")
def update_user_password(
    username: str,
    request: UserPasswordUpdateRequest,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    violations = password_policy_errors(request.password)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password does not meet requirements: " + "; ".join(violations),
        )

    with SessionLocal() as session:
        user = session.scalar(
            select(UserModel).where(UserModel.username == username.strip().lower())
        )
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        user.password_hash = hash_password(request.password)
        audit.record_security_event(
            action="user.password.reset",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="user",
            resource_id=str(user.id),
            request=http_request,
            session=session,
        )
        session.commit()

    return {"message": "Password updated successfully"}


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    username: str,
    request: Request,
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
        audit.record_security_event(
            action="user.delete",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="user",
            resource_id=str(user.id),
            request=request,
            session=session,
        )
        session.delete(user)
        session.commit()