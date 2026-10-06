from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from pydantic import BaseModel
from observa.database.database import engine
from observa.database.repositories import DetectorRepository, SourceRepository
from observa.database.database import SessionLocal
from observa.database.models import UserModel
from observa.auth.security import create_access_token, verify_password
from observa.auth.dependencies import AuthenticatedUser, require_roles
from observa.security import audit
from typing import List

router = APIRouter()
class DeleteRequest(BaseModel):
    names: List[str]


class LoginRequest(BaseModel):
    username: str
    password: str
        
@router.delete("/clear")
def clear_database(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_roles("admin")),
):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE sources, detectors, history RESTART IDENTITY CASCADE;"))
        audit.record_security_event(
            action="database.clear",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="database",
            resource_id="observa",
            request=request,
            connection=conn,
        )
    return {"message": "✅ Database cleared successfully"}

@router.delete("/sources")
def delete_sources(
    req: DeleteRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    SourceRepository.delete_batch(req.names)
    for name in req.names:
        audit.record_security_event(
            action="source.delete",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="source",
            resource_id=name,
            request=request,
        )
    return {"message": f"Deleted sources: {', '.join(req.names)}"}

@router.delete("/detectors")
def delete_detectors(
    req: DeleteRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    DetectorRepository.delete_batch(req.names)
    for name in req.names:
        audit.record_security_event(
            action="detector.delete",
            outcome="success",
            actor_user_id=current_user.id,
            resource_type="detector",
            resource_id=name,
            request=request,
        )
    return {"message": f"Deleted detectors: {', '.join(req.names)}"}

@router.post("/login")
def login(data: LoginRequest, request: Request):
    username = data.username.strip().lower()
    with SessionLocal() as session:
        user = session.query(UserModel).filter(UserModel.username == username).first()
        if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
            audit.record_security_event(
                action="auth.login",
                outcome="failure",
                actor_user_id=None,
                resource_type="user",
                resource_id=username,
                request=request,
                session=session,
            )
            session.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = create_access_token(username=user.username, role=user.role)
        audit.record_security_event(
            action="auth.login",
            outcome="success",
            actor_user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            request=request,
            session=session,
        )
        session.commit()
        return {
            "success": True,
            "token": token,
            "token_type": "bearer",
            "expires_in": 900,
            "username": user.username,
            "role": user.role,
        }