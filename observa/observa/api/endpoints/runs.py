from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from observa.framework.orchestrator import global_orchestrator as orchestrator
from observa.framework.manager import global_manager as manager
from observa.sources.data_source import DataSource
from observa.sources.remote_source import RemoteSource
from observa.detectors.remote_detector import RemoteDetector
from typing import List, Dict, Any
from datetime import datetime, timedelta
import importlib
from observa.auth.dependencies import AuthenticatedUser, require_roles

router = APIRouter()


def get_source_or_404(name: str):
    source = manager.get_source(name)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    return source


def get_detector_or_404(name: str):
    detector = manager.get_detector(name)
    if detector is None:
        raise HTTPException(status_code=404, detail=f"Detector '{name}' not found")
    return detector


class RunRequest(BaseModel):
    sources: List[str]
    detectors: List[str]

@router.post('/execute')
def execute_run(
    req: RunRequest,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator", "executor")),
):
    result = []    
    try:
        for src in req.sources:
            for det in req.detectors:
                source = get_source_or_404(src)
                detector = get_detector_or_404(det)
                if source.api_url:
                    sourceObj = RemoteSource(name=source.name, api_url=source.api_url)    
                else:
                    sourceObj = DataSource(name=source.name, json_data=source.json_data)                    
                
                if detector.api_url:
                    detectorObj = RemoteDetector(nameAP=detector.name_ap, name=detector.name, api_url=detector.api_url)
                else:
                    module_name, class_name = detector.class_path.rsplit('.', 1)
                    module = importlib.import_module(module_name)
                    cls = getattr(module, class_name)
                    detectorObj = cls(nameAP=detector.name_ap,name=detector.name)

                resultTemp = orchestrator.run(source=sourceObj, detector=detectorObj)                    
                manager.register_history(source_id=source.id, detector_id=detector.id, result=resultTemp)
                    
                result.append(resultTemp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result

@router.post('/autorun')
def autorun(
    payload: Dict[str, Any] = Body(...),
    _: AuthenticatedUser = Depends(require_roles("admin", "operator", "executor")),
):
    source_name = payload.get("source_name")
    data = payload.get("data")
    detector = payload.get("detector")
    
    result = [] 
    try:
        source = get_source_or_404(source_name)
        detector = get_detector_or_404(detector)
        if detector.api_url:
            detectorObj = RemoteDetector(nameAP=detector.name_ap, name=detector.name, api_url=detector.api_url)
        else:
            module_name, class_name = detector.class_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            detectorObj = cls(nameAP=detector.name_ap,name=detector.name)
    
        resultTemp = orchestrator.autorun(source_name=source_name, detector=detectorObj, data=data)
        manager.register_history(source_id=source.id, detector_id=detector.id, result=resultTemp)               
        result.append(resultTemp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result

@router.post('/collect')
def execute_run(
    req: RunRequest,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator", "executor")),
):
    result = []    
    try:
        for src in req.sources:
            source = get_source_or_404(src)
            if source.api_url:
                sourceObj = RemoteSource(name=source.name, api_url=source.api_url)    
            else:
                sourceObj = DataSource(name=source.name, json_data=source.json_data)                    
            
            result.append(sourceObj.load())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result

@router.get('/history')
def execute_history(
    source: str,
    detector: str,
    start: str,
    end: str,
    _: AuthenticatedUser = Depends(require_roles("admin", "operator")),
):
    source = get_source_or_404(source)
    detector = get_detector_or_404(detector)

    try:
        start_dt = datetime.fromisoformat(start) + timedelta(hours=3)
        end_dt = datetime.fromisoformat(end) + timedelta(hours=3)
        if start_dt > end_dt:
            raise ValueError("start must not be after end")
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid date range. Provide ISO 8601 start and end values with start before or equal to end.",
        ) from exc
    
    history = manager.get_history(source_id=source.id,detector_id=detector.id, start=start_dt, end=end_dt)
    
    response = {
        "source": source,
        "detector": detector,
        "history": history
    }
        
    return response
    
    