from observa.database.database import SessionLocal
from observa.database.models import SourceModel, DetectorModel, HistoryModel
from datetime import datetime
from observa.security.telemetry_masking import mask_telemetry

class SourceRepository:
    @staticmethod
    def add_source(name: str, api_url: str = None, json_content: dict = None):
        db = SessionLocal()
        src = SourceModel(
            name=name,
            api_url=api_url,
            json_data=mask_telemetry(json_content) if json_content is not None else None,
        )
        db.add(src)
        db.commit()
        db.close()

    @staticmethod
    def get_all():
        db = SessionLocal()
        sources = db.query(SourceModel).all()
        db.close()
        return sources

    @staticmethod
    def get_by_name(name: str):
        db = SessionLocal()
        source = db.query(SourceModel).filter(SourceModel.name == name).first()
        db.close()
        return source
    
    @staticmethod
    def delete_batch(names: list[str]):
        db = SessionLocal()
        db.query(SourceModel).filter(SourceModel.name.in_(names)).delete(synchronize_session=False)
        db.commit()  
        db.close()

class DetectorRepository:
    @staticmethod
    def add_detector(name_ap: str, name: str, class_path: str = None, api_url: str = None):
        db = SessionLocal()
        det = DetectorModel(name_ap=name_ap, name=name, class_path=class_path, api_url=api_url)
        db.add(det)
        db.commit()
        db.close()

    @staticmethod
    def get_all():
        db = SessionLocal()
        detectors = db.query(DetectorModel).all()
        db.close()
        return detectors

    @staticmethod
    def get_by_name(name: str):
        db = SessionLocal()
        det = db.query(DetectorModel).filter(DetectorModel.name == name).first()
        db.close()
        return det

    @staticmethod
    def delete_batch(names: list[str]):
        db = SessionLocal()
        db.query(DetectorModel).filter(DetectorModel.name.in_(names)).delete(synchronize_session=False)
        db.commit()  
        db.close()
        
class HistoryRepository:
    @staticmethod
    def add_history(source_id: int, detector_id: int, detected: int, total: int, execution_time: int, result: dict):
        db = SessionLocal()
        entry = HistoryModel(
            source_id=source_id,
            detector_id=detector_id,
            detected=detected,
            total=total,
            execution_time=execution_time,
            result=mask_telemetry(result),
        )
        db.add(entry)
        db.commit()
        db.close()

    @staticmethod
    def get_by_source_and_detector(source_id: int, detector_id: int, start: datetime, end: datetime):
        db = SessionLocal()
        history = db.query(HistoryModel).filter(
            HistoryModel.source_id == source_id,
            HistoryModel.detector_id == detector_id,
            HistoryModel.timestamp >= start,
            HistoryModel.timestamp <= end).order_by(HistoryModel.timestamp.asc()).all()
        db.close()
        return history