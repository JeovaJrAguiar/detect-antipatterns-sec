from observa.database import repositories
from observa.api.endpoints import runs
from observa.auth.dependencies import AuthenticatedUser
from observa.framework.orchestrator import Orchestrator
from types import SimpleNamespace
from unittest.mock import Mock


USER = AuthenticatedUser(id=7, username="operator", role="operator")


class CapturingDetector:
    nameAP = "sample-antipattern"
    name = "sample-detector"

    def __init__(self):
        self.received_data = None

    def detect(self, data):
        self.received_data = data
        return {"analyzed": len(data), "detected": 0, "data": data}


class StaticSource:
    name = "sample-source"

    def __init__(self, data):
        self.data = data

    def load(self):
        return self.data


def test_orchestrator_masks_telemetry_before_detector_and_result():
    source_data = [{"count": 15, "email": "ana@example.com"}]
    detector = CapturingDetector()

    result = Orchestrator().run(detector=detector, source=StaticSource(source_data))

    expected = [{"count": 15, "email": "[REDACTED]"}]
    assert detector.received_data == expected
    assert result["data"] == expected
    assert source_data == [{"count": 15, "email": "ana@example.com"}]


def test_autorun_masks_client_supplied_data_before_detector():
    source_data = [{"quantidade": 12, "customer": {"cpf": "123.456.789-00"}}]
    detector = CapturingDetector()

    result = Orchestrator().autorun(
        detector=detector,
        data=source_data,
        source_name="client-source",
    )

    expected = [{"quantidade": 12, "customer": {"cpf": "[REDACTED]"}}]
    assert detector.received_data == expected
    assert result["data"] == expected
    assert source_data[0]["customer"]["cpf"] == "123.456.789-00"


def test_source_repository_masks_local_source_data_before_commit(monkeypatch):
    persisted = []

    class Session:
        def add(self, model):
            persisted.append(model)

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(repositories, "SessionLocal", Session)
    payload = [{"count": 2, "email": "ana@example.com"}]

    repositories.SourceRepository.add_source("source-a", json_content=payload)

    assert persisted[0].json_data == [{"count": 2, "email": "[REDACTED]"}]
    assert payload[0]["email"] == "ana@example.com"


def test_history_repository_masks_result_before_commit(monkeypatch):
    persisted = []

    class Session:
        def add(self, model):
            persisted.append(model)

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(repositories, "SessionLocal", Session)
    result = [{"count": 2, "email": "ana@example.com"}]

    repositories.HistoryRepository.add_history(
        source_id=1,
        detector_id=2,
        detected=0,
        total=1,
        execution_time=3.5,
        result=result,
    )

    assert persisted[0].result == [{"count": 2, "email": "[REDACTED]"}]
    assert result[0]["email"] == "ana@example.com"


def test_collect_masks_telemetry_before_returning_to_client(monkeypatch):
    source_model = SimpleNamespace(
        name="source-a",
        api_url=None,
        json_data=[{"count": 2, "email": "ana@example.com"}],
    )
    monkeypatch.setattr(runs, "get_source_or_404", lambda name: source_model)
    monkeypatch.setattr(
        runs,
        "DataSource",
        lambda **kwargs: StaticSource(kwargs["json_data"]),
    )
    monkeypatch.setattr(runs, "audit_run_event", Mock())
    collect_endpoint = next(
        route.endpoint for route in runs.router.routes if route.path == "/collect"
    )

    result = collect_endpoint(
        runs.RunRequest(sources=["source-a"], detectors=[]),
        None,
        USER,
    )

    assert result == [[{"count": 2, "email": "[REDACTED]"}]]
