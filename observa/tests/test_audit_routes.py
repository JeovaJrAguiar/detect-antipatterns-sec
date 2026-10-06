from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from observa.api.endpoints import clear, runs
from observa.api.endpoints import users as user_endpoints
from observa.api.endpoints.clear import LoginRequest
from observa.api.endpoints.runs import RunRequest
from observa.api.endpoints.users import UserCreateRequest
from observa.auth.dependencies import AuthenticatedUser
from observa.database.models import SecurityAuditLogModel, UserModel
from observa.security import audit


USER = AuthenticatedUser(id=41, username="admin", role="admin")
REQUEST_ID = "372ea4a3-68d2-4b7c-bad3-d4231258250e"


def _request():
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/test",
            "headers": [],
            "client": ("198.51.100.20", 54321),
            "state": {"request_id": REQUEST_ID, "user_id": USER.id},
        }
    )


def _endpoint(router, path, method="POST"):
    return next(
        route.endpoint
        for route in router.routes
        if route.path == path and method in route.methods
    )


def test_failed_login_is_audited_without_recording_password(monkeypatch):
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def query(self, model):
            return self

        def filter(self, condition):
            return self

        def first(self):
            return None

        def commit(self):
            pass

    record = Mock()
    monkeypatch.setattr(clear, "SessionLocal", FakeSession)
    monkeypatch.setattr(audit, "record_security_event", record)

    with pytest.raises(HTTPException) as error:
        _endpoint(clear.router, "/login")(
            LoginRequest(username="unknown", password="do-not-store-this"),
            _request(),
        )

    assert error.value.status_code == 401
    event = record.call_args.kwargs
    assert event["action"] == "auth.login"
    assert event["outcome"] == "failure"
    assert event["actor_user_id"] is None
    assert "do-not-store-this" not in repr(event)


def test_successful_login_is_audited_with_user_id(monkeypatch):
    user = SimpleNamespace(
        id=41,
        username="admin",
        role="admin",
        is_active=True,
        password_hash="hashed-password",
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def query(self, model):
            return self

        def filter(self, condition):
            return self

        def first(self):
            return user

        def commit(self):
            pass

    record = Mock()
    monkeypatch.setattr(clear, "SessionLocal", FakeSession)
    monkeypatch.setattr(clear, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(clear, "create_access_token", lambda **kwargs: "signed-token")
    monkeypatch.setattr(audit, "record_security_event", record)

    response = _endpoint(clear.router, "/login")(
        LoginRequest(username="admin", password="correct-secret"), _request()
    )

    assert response["token"] == "signed-token"
    event = record.call_args.kwargs
    assert event["action"] == "auth.login"
    assert event["outcome"] == "success"
    assert event["actor_user_id"] == user.id


def test_run_execution_is_audited_without_telemetry(monkeypatch):
    source = SimpleNamespace(id=101, name="source-a", api_url="https://source.example")
    detector = SimpleNamespace(
        id=202,
        name="detector-a",
        name_ap="ap-a",
        api_url="https://detector.example",
    )
    manager = SimpleNamespace(
        get_source=Mock(return_value=source),
        get_detector=Mock(return_value=detector),
        register_history=Mock(),
    )
    orchestrator = SimpleNamespace(run=Mock(return_value={"data": [{"private": "payload"}]}))
    record = Mock()
    monkeypatch.setattr(runs, "manager", manager)
    monkeypatch.setattr(runs, "orchestrator", orchestrator)
    monkeypatch.setattr(runs, "RemoteSource", lambda **kwargs: object())
    monkeypatch.setattr(runs, "RemoteDetector", lambda **kwargs: object())
    monkeypatch.setattr(audit, "record_security_event", record)

    response = _endpoint(runs.router, "/execute")(
        RunRequest(sources=["source-a"], detectors=["detector-a"]),
        _request(),
        USER,
    )

    assert response == [{"data": [{"private": "payload"}]}]
    event = record.call_args.kwargs
    assert event["action"] == "run.execute"
    assert event["outcome"] == "success"
    assert event["actor_user_id"] == USER.id
    assert "private" not in repr(event)


def test_clear_audit_event_shares_transaction_and_excludes_audit_table(monkeypatch):
    statements = []
    record = Mock()

    class Connection:
        def execute(self, statement):
            statements.append(str(statement))

    @contextmanager
    def begin():
        yield Connection()

    monkeypatch.setattr(clear, "engine", SimpleNamespace(begin=begin))
    monkeypatch.setattr(audit, "record_security_event", record)

    response = _endpoint(clear.router, "/clear", method="DELETE")(_request(), USER)

    assert response["message"]
    assert "security_audit_log" not in statements[0]
    event = record.call_args.kwargs
    assert event["action"] == "database.clear"
    assert event["outcome"] == "success"
    assert event["actor_user_id"] == USER.id


def test_user_creation_and_deletion_keep_audit_rows_after_account_removal(monkeypatch):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://")
    UserModel.__table__.create(engine)
    SecurityAuditLogModel.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(user_endpoints, "SessionLocal", session_factory)
    monkeypatch.setattr(user_endpoints, "hash_password", lambda password: "hashed")

    response = _endpoint(user_endpoints.router, "/users")(
        UserCreateRequest(username="new-operator", role="operator"),
        _request(),
        USER,
    )
    created_user_id = response["user"]["username"]

    with session_factory() as session:
        created_user = session.scalar(
            select(UserModel).where(UserModel.username == created_user_id)
        )
        assert created_user is not None
        audit_rows = session.scalars(select(SecurityAuditLogModel)).all()
        assert [(row.action, row.actor_user_id) for row in audit_rows] == [
            ("user.create", USER.id)
        ]
        assert audit_rows[0].client_ip == "198.51.100.20"
        assert audit_rows[0].request_id == REQUEST_ID
        user_database_id = created_user.id

    _endpoint(user_endpoints.router, "/users/{username}", method="DELETE")(
        "new-operator", _request(), USER
    )

    with session_factory() as session:
        assert session.get(UserModel, user_database_id) is None
        audit_rows = session.scalars(
            select(SecurityAuditLogModel).order_by(SecurityAuditLogModel.id)
        ).all()
        assert [row.action for row in audit_rows] == ["user.create", "user.delete"]
        assert all(row.actor_user_id == USER.id for row in audit_rows)

    engine.dispose()


def test_audited_routers_register_with_fastapi():
    from observa.api.endpoints import detectors, sources

    app = FastAPI()
    for router in (clear.router, user_endpoints.router, runs.router, sources.router, detectors.router):
        app.include_router(router)

    assert "/login" in {route.path for route in app.routes}
    assert "/execute" in {route.path for route in app.routes}
    assert "/users" in {route.path for route in app.routes}
