from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from observa.auth.dependencies import AuthenticatedUser, require_roles
from observa.framework.manager import global_manager as manager
from observa.security.ssrf_guard import validate_remote_url
from observa.sources.data_source import DataSource
from observa.sources.remote_source import RemoteSource

router = APIRouter()

class SourceRegisterRequest(BaseModel):
    name: str
    api_url: Any
    json_data: Any

@router.post('/register')
def register_source(
    req: SourceRegisterRequest,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    try:
        safe_url = validate_remote_url(req.api_url) if req.api_url else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if safe_url:
        source = RemoteSource(name=req.name, api_url=safe_url)
    else:
        source = DataSource(name=req.name, json_data=req.json_data)
    if source:
        manager.register_source(source)
        return {'message': f"Source '{source.name}' registered"}
    else:
        return {'message': 'error'}

@router.get('/list')
def list_sources(_: AuthenticatedUser = Depends(require_roles("admin", "operator", "executor"))):
    return {'sources': manager.list_sources()}

@router.get('/get')
def get_source(
    name: str,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    return {'source': manager.get_source(name)}