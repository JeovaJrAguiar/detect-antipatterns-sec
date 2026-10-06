from typing import Optional

from fastapi import Request
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from observa.database.database import SessionLocal
from observa.database.models import SecurityAuditLogModel


def record_security_event(
    *,
    action: str,
    outcome: str,
    actor_user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    client_ip: Optional[str] = None,
    request_id: Optional[str] = None,
    session: Optional[Session] = None,
    connection: Optional[Connection] = None,
) -> None:
    if request is not None:
        if actor_user_id is None:
            actor_user_id = getattr(request.state, "user_id", None)
        if client_ip is None and request.client is not None:
            client_ip = request.client.host
        if request_id is None:
            request_id = getattr(request.state, "request_id", None)
    if request_id == "-":
        request_id = None
    if resource_id is not None:
        resource_id = str(resource_id)[:255]

    event_values = {
        "actor_user_id": actor_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outcome": outcome,
        "client_ip": client_ip,
        "request_id": request_id,
    }
    if session is not None:
        session.add(SecurityAuditLogModel(**event_values))
        return
    if connection is not None:
        connection.execute(SecurityAuditLogModel.__table__.insert().values(**event_values))
        return

    with SessionLocal() as session:
        session.add(SecurityAuditLogModel(**event_values))
        session.commit()