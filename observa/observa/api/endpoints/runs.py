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
                source = manager.get_source(src)                
                if source.api_url:
                    sourceObj = RemoteSource(name=source.name, api_url=source.api_url)    
                else:
                    sourceObj = DataSource(name=source.name, json_data=source.json_data)                    
                
                detector = manager.get_detector(det)                
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
        detector = manager.get_detector(detector)                
        if detector.api_url:
            detectorObj = RemoteDetector(nameAP=detector.name_ap, name=detector.name, api_url=detector.api_url)
        else:
            module_name, class_name = detector.class_path.rsplit('.', 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            detectorObj = cls(nameAP=detector.name_ap,name=detector.name)
    
        resultTemp = orchestrator.autorun(source_name=source_name, detector=detectorObj, data=data)  
        source = manager.get_source(source_name)                
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
            source = manager.get_source(src)                
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
    source = manager.get_source(source)
    detector = manager.get_detector(detector)
    
    start_dt = datetime.fromisoformat(start) + timedelta(hours=3)
    end_dt = datetime.fromisoformat(end) + timedelta(hours=3)
    
    history = manager.get_history(source_id=source.id,detector_id=detector.id, start=start_dt, end=end_dt)
    
    response = {
        "source": source,
        "detector": detector,
        "history": history
    }
        
    return response
    
    