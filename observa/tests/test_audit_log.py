from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
import pytest

from observa.database.models import SecurityAuditLogModel
from observa.security import audit


def test_audit_events_persist_context_and_reject_mutations(monkeypatch):
    engine = create_engine("sqlite://")
    SecurityAuditLogModel.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(audit, "SessionLocal", session_factory)

    audit.record_security_event(
        action="auth.login",
        outcome="failure",
        actor_user_id=None,
        resource_type="authentication",
        resource_id="login",
        client_ip="192.0.2.10",
        request_id="d7977caa-c81c-40c4-8175-86b5df8fbd13",
    )
    audit.record_security_event(
        action="source.create",
        outcome="success",
        resource_type="source",
        resource_id="r" * 300,
    )

    with session_factory() as session:
        event = session.scalar(select(SecurityAuditLogModel))
        assert event.actor_user_id is None
        assert event.action == "auth.login"
        assert event.outcome == "failure"
        assert event.client_ip == "192.0.2.10"
        assert event.request_id == "d7977caa-c81c-40c4-8175-86b5df8fbd13"
        event_id = event.id
        long_resource = session.scalar(
            select(SecurityAuditLogModel).where(SecurityAuditLogModel.action == "source.create")
        )
        assert len(long_resource.resource_id) == 255

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                update(SecurityAuditLogModel)
                .where(SecurityAuditLogModel.id == event_id)
                .values(outcome="success")
            )

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                delete(SecurityAuditLogModel).where(SecurityAuditLogModel.id == event_id)
            )

    audit.record_security_event(
        action="auth.login",
        outcome="success",
        actor_user_id=9342,
        resource_type="authentication",
        resource_id="login",
    )
    with engine.begin() as connection:
        audit.record_security_event(
            action="database.clear",
            outcome="success",
            actor_user_id=9342,
            resource_type="database",
            resource_id="observa",
            connection=connection,
        )
    with session_factory() as session:
        assert len(session.scalars(select(SecurityAuditLogModel)).all()) == 4

    engine.dispose()