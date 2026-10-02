from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from pydantic import BaseModel
from observa.database.database import engine
from observa.database.repositories import DetectorRepository, SourceRepository
from observa.database.database import SessionLocal
from observa.database.models import UserModel
from observa.auth.security import create_access_token, verify_password
from observa.auth.dependencies import AuthenticatedUser, require_roles
from typing import List

router = APIRouter()
class DeleteRequest(BaseModel):
    names: List[str]


class LoginRequest(BaseModel):
    username: str
    password: str
        
@router.delete("/clear")
def clear_database(_: AuthenticatedUser = Depends(require_roles("admin"))):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE sources, detectors, history RESTART IDENTITY CASCADE;"))
    return {"message": "✅ Database cleared successfully"}

@router.delete("/sources")
def delete_sources(
    req: DeleteRequest,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    SourceRepository.delete_batch(req.names)
    return {"message": f"Deleted sources: {', '.join(req.names)}"}

@router.delete("/detectors")
def delete_detectors(
    req: DeleteRequest,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    DetectorRepository.delete_batch(req.names)
    return {"message": f"Deleted detectors: {', '.join(req.names)}"}

@router.post("/login")
def login(data: LoginRequest):
    username = data.username.strip().lower()
    with SessionLocal() as session:
        user = session.query(UserModel).filter(UserModel.username == username).first()
        if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = create_access_token(username=user.username, role=user.role)
        return {
            "success": True,
            "token": token,
            "token_type": "bearer",
            "expires_in": 900,
            "username": user.username,
            "role": user.role,
        }