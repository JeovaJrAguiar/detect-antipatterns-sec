from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from observa.auth.dependencies import AuthenticatedUser, require_roles
from observa.framework.manager import global_manager as manager
from observa.security.ssrf_guard import validate_remote_url

router = APIRouter()
_manager = manager

class DetectorRegisterRequest(BaseModel):
    antipattern: str
    name: str
    api_url: str = None

@router.post('/register')
def register_detector(
    req: DetectorRegisterRequest,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    try:
        safe_url = validate_remote_url(req.api_url) if req.api_url else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _manager.register_detector(name_ap=req.antipattern, name=req.name, api_url=safe_url)
    return {'message': f"Detector '{req.name}' registered"}

@router.get('/list')
def list_detectors(_: AuthenticatedUser = Depends(require_roles("admin", "operator", "executor"))):
    return {'detectors': _manager.list_detectors()}

@router.get('/get')
def get_detector(
    name: str,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    return {'detector': _manager.get_detector(name)}
