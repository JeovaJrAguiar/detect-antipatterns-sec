from observa.sources.json_source import JsonSource
from observa.framework.manager import global_manager as manager
from observa.framework.base import Source, Detector
from dotenv import load_dotenv
from typing import Dict, Any, List
import time
import os
import importlib

class Orchestrator:
    def load(self):
        print("\n####### Observa Framework #######\n")
        
        load_dotenv()
        print("Loaded environment variables ...")

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

        print("\n####### Available sources #######\n")

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
            
        for item in set(manager.list_sources()):
            print(item)

        _names_detectors = [item.strip() for item in DETECTOR_LOCAL_NAME.split(',') if item.strip()]
        _path_detectors = [item.strip() for item in DETECTOR_LOCAL_PATH.split(',') if item.strip()]
        _aps = [item.strip() for item in DETECTOR_LOCAL_AP.split(',') if item.strip()]       

        print("\n####### Available detectors #######\n")

        for i, value in enumerate(_names_detectors):
            if not manager.get_detector(value):
                manager.register_detector(name_ap=_aps[i], name=value, class_path=_path_detectors[i])

        for item in set(manager.list_detectors()):
            print(item.name_ap + " - " + item.name)
                
        print("\nReady !!!\n")
        
    def run(self, detector: Detector, source: Source) -> Dict[str, Any]: 
        data = source.load()
        start = time.time()        
        result = detector.detect(data)        
        end = time.time()   
        result.setdefault('ap', detector.nameAP)
        result.setdefault('source', source.name)        
        result.setdefault('detector', detector.name)
        result.setdefault('execution_time_ms', round((end - start) * 1000, 3))
        return result
    
    def autorun(self, detector: Detector, data: List[Dict[str, Any]], source_name: str) -> Dict[str, Any]: 
        data = data
        start = time.time()        
        result = detector.detect(data)        
        end = time.time()       
        result.setdefault('ap', detector.nameAP)
        result.setdefault('source', source_name)        
        result.setdefault('detector', detector.name)
        result.setdefault('execution_time_ms', round((end - start) * 1000, 3))
        return result
        
global_orchestrator = Orchestrator()    