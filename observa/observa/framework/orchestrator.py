from observa.sources.json_source import JsonSource
from observa.framework.manager import global_manager as manager
from observa.framework.base import Source, Detector
from dotenv import load_dotenv
from typing import Dict, Any, List
import logging
import time
import os
import importlib
from observa.security.telemetry_masking import TelemetryMaskingProcessor

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.telemetry_masker = None

    def load(self):
        logger.info("orchestrator_starting")
        load_dotenv()
        self.telemetry_masker = TelemetryMaskingProcessor.from_environment()

        SOURCES_LOCAL_NAME = os.getenv("SOURCES_LOCAL_NAME", "")
        SOURCES_LOCAL_PATH = os.getenv("SOURCES_LOCAL_PATH", "")
        SOURCES_LOCAL_OBJECT_NAME = os.getenv("SOURCES_LOCAL_OBJECT_NAME", "")
        SOURCES_LOCAL_OBJECT_PACKAGE = os.getenv("SOURCES_LOCAL_OBJECT_PACKAGE", "")
        DETECTOR_LOCAL_AP = os.getenv("DETECTOR_LOCAL_AP", "")
        DETECTOR_LOCAL_NAME = os.getenv("DETECTOR_LOCAL_NAME", "")
        DETECTOR_LOCAL_PATH = os.getenv("DETECTOR_LOCAL_PATH", "")

        _names_source = [item.strip() for item in SOURCES_LOCAL_NAME.split(',') if item.strip()]
        _paths_source = [item.strip() for item in SOURCES_LOCAL_PATH.split(',') if item.strip()]
        _namesObject_source = [item.strip() for item in SOURCES_LOCAL_OBJECT_NAME.split(',') if item.strip()]
        _packagesObject_source = [item.strip() for item in SOURCES_LOCAL_OBJECT_PACKAGE.split(',') if item.strip()]

        for i, value in enumerate(_names_source):
            if not manager.get_source(value):
                _json = JsonSource(name=value,path=_paths_source[i])        
                manager.register_source(_json)
                
        for i, value in enumerate(_namesObject_source):
            if not manager.get_source(value):           
                module_name, class_name = _packagesObject_source[i].rsplit('.', 1)
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                source = cls(name=value)
                manager.register_source(source)                
            
        _names_detectors = [item.strip() for item in DETECTOR_LOCAL_NAME.split(',') if item.strip()]
        _path_detectors = [item.strip() for item in DETECTOR_LOCAL_PATH.split(',') if item.strip()]
        _aps = [item.strip() for item in DETECTOR_LOCAL_AP.split(',') if item.strip()]       

        for i, value in enumerate(_names_detectors):
            if not manager.get_detector(value):
                manager.register_detector(name_ap=_aps[i], name=value, class_path=_path_detectors[i])

        logger.info(
            "orchestrator_ready",
            extra={
                "source_count": len(manager.list_sources()),
                "detector_count": len(manager.list_detectors()),
            },
        )
        
    def run(self, detector: Detector, source: Source) -> Dict[str, Any]: 
        data = self._mask_telemetry(source.load())
        start = time.time()        
        result = detector.detect(data)        
        end = time.time()   
        result.setdefault('ap', detector.nameAP)
        result.setdefault('source', source.name)        
        result.setdefault('detector', detector.name)
        result.setdefault('execution_time_ms', round((end - start) * 1000, 3))
        return self._mask_telemetry(result)
    
    def autorun(self, detector: Detector, data: List[Dict[str, Any]], source_name: str) -> Dict[str, Any]: 
        data = self._mask_telemetry(data)
        start = time.time()        
        result = detector.detect(data)        
        end = time.time()       
        result.setdefault('ap', detector.nameAP)
        result.setdefault('source', source_name)        
        result.setdefault('detector', detector.name)
        result.setdefault('execution_time_ms', round((end - start) * 1000, 3))
        return self._mask_telemetry(result)

    def _mask_telemetry(self, data: Any) -> Any:
        if self.telemetry_masker is None:
            self.telemetry_masker = TelemetryMaskingProcessor.from_environment()
        return self.telemetry_masker.process(data)
        
global_orchestrator = Orchestrator()    