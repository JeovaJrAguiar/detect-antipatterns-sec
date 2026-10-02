from fastapi import APIRouter, Depends
from pydantic import BaseModel
from observa.framework.manager import global_manager as manager
from observa.sources.data_source import DataSource
from observa.sources.remote_source import RemoteSource
from typing import Any
from observa.auth.dependencies import AuthenticatedUser, require_roles

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
    if req.api_url:
        source = RemoteSource(name=req.name, api_url=req.api_url)    
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