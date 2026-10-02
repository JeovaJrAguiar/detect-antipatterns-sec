from fastapi import APIRouter, Depends
from pydantic import BaseModel
from observa.framework.manager import global_manager as manager
from observa.auth.dependencies import AuthenticatedUser, require_roles

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
    _manager.register_detector(name_ap=req.antipattern, name=req.name, api_url=req.api_url)
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
