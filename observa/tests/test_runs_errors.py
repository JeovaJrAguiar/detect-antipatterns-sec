from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from observa.api.endpoints import runs
from observa.auth.dependencies import AuthenticatedUser
from observa.api.endpoints.runs import RunRequest


USER = AuthenticatedUser(id=7, username="operator", role="operator")


def _endpoint(path, method="POST"):
    return next(
        route.endpoint
        for route in runs.router.routes
        if route.path == path and method in route.methods
    )


def _source():
    return SimpleNamespace(
        id=11,
        name="source-a",
        api_url=None,
        json_data={"items": []},
    )


def _remote_detector():
    return SimpleNamespace(
        id=22,
        name="detector-a",
        name_ap="antipattern-a",
        api_url="https://detector.example/api",
    )


def test_execute_returns_404_when_source_is_missing(monkeypatch):
    manager = SimpleNamespace(get_source=Mock(return_value=None))
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/execute")(
            RunRequest(sources=["missing-source"], detectors=["detector-a"]), USER
        )

    assert error.value.status_code == 404


def test_execute_returns_404_when_detector_is_missing(monkeypatch):
    manager = SimpleNamespace(
        get_source=Mock(return_value=_source()),
        get_detector=Mock(return_value=None),
    )
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/execute")(
            RunRequest(sources=["source-a"], detectors=["missing-detector"]), USER
        )

    assert error.value.status_code == 404


def test_autorun_returns_404_when_detector_is_missing(monkeypatch):
    manager = SimpleNamespace(
        get_source=Mock(return_value=_source()),
        get_detector=Mock(return_value=None),
    )
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/autorun")(
            {"source_name": "source-a", "detector": "missing-detector", "data": []},
            USER,
        )

    assert error.value.status_code == 404


def test_autorun_returns_404_for_missing_source_before_running_detector(monkeypatch):
    detector = _remote_detector()
    manager = SimpleNamespace(
        get_detector=Mock(return_value=detector),
        get_source=Mock(return_value=None),
    )
    orchestrator = SimpleNamespace(autorun=Mock())
    monkeypatch.setattr(runs, "manager", manager)
    monkeypatch.setattr(runs, "orchestrator", orchestrator)
    monkeypatch.setattr(runs, "RemoteDetector", lambda **kwargs: object())

    with pytest.raises(HTTPException) as error:
        _endpoint("/autorun")(
            {"source_name": "missing-source", "detector": "detector-a", "data": []},
            USER,
        )

    assert error.value.status_code == 404
    orchestrator.autorun.assert_not_called()


def test_collect_returns_404_when_source_is_missing(monkeypatch):
    manager = SimpleNamespace(get_source=Mock(return_value=None))
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/collect")(
            RunRequest(sources=["missing-source"], detectors=[]), USER
        )

    assert error.value.status_code == 404


@pytest.mark.parametrize(
    ("source", "detector", "start", "end", "missing_entity"),
    [
        (None, object(), "2026-01-01", "2026-01-02", "source"),
        (object(), None, "2026-01-01", "2026-01-02", "detector"),
    ],
)
def test_history_returns_404_when_entity_is_missing(
    monkeypatch, source, detector, start, end, missing_entity
):
    manager = SimpleNamespace(
        get_source=Mock(return_value=source),
        get_detector=Mock(return_value=detector),
    )
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/history", method="GET")(
            source="source-a",
            detector="detector-a",
            start=start,
            end=end,
            _=USER,
        )

    assert error.value.status_code == 404
    assert missing_entity in error.value.detail.lower()


def test_history_returns_400_for_invalid_dates(monkeypatch):
    manager = SimpleNamespace(
        get_source=Mock(return_value=_source()),
        get_detector=Mock(return_value=_remote_detector()),
    )
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/history", method="GET")(
            source="source-a",
            detector="detector-a",
            start="not-a-date",
            end="2026-01-02",
            _=USER,
        )

    assert error.value.status_code == 400


def test_history_returns_400_when_start_is_after_end(monkeypatch):
    manager = SimpleNamespace(
        get_source=Mock(return_value=_source()),
        get_detector=Mock(return_value=_remote_detector()),
    )
    monkeypatch.setattr(runs, "manager", manager)

    with pytest.raises(HTTPException) as error:
        _endpoint("/history", method="GET")(
            source="source-a",
            detector="detector-a",
            start="2026-01-03",
            end="2026-01-02",
            _=USER,
        )

    assert error.value.status_code == 400