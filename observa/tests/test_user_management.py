import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from observa.api.endpoints import users
from observa.api.endpoints import clear
from observa.auth import dependencies
from observa.auth.dependencies import AuthenticatedUser
from observa.auth.security import generate_strong_password, password_policy_errors
from observa.database.models import UserModel
from observa.auth.bootstrap_dev_users import DEVELOPMENT_USERS


ADMIN = AuthenticatedUser(id=1, username="admin", role="admin")
OPERATOR = AuthenticatedUser(id=2, username="operator", role="operator")


def _request():
    return Request(
        {
            "type": "http",
            "method": "PATCH",
            "path": "/api/v1/admin/users",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "state": {"user_id": ADMIN.id},
        }
    )


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite://")
    UserModel.__table__.create(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(users, "SessionLocal", factory)
    monkeypatch.setattr(dependencies, "SessionLocal", factory)
    monkeypatch.setattr(users.audit, "record_security_event", Mock())

    with factory() as session:
        session.add_all(
            [
                UserModel(
                    id=ADMIN.id,
                    username=ADMIN.username,
                    email="admin@observa.com",
                    password_hash="admin-hash",
                    role=ADMIN.role,
                    is_active=True,
                ),
                UserModel(
                    id=OPERATOR.id,
                    username=OPERATOR.username,
                    email="operador@observa.com",
                    password_hash="operator-hash",
                    role=OPERATOR.role,
                    is_active=True,
                ),
            ]
        )
        session.commit()

    yield factory
    engine.dispose()


def _endpoint(path, method):
    return next(
        route.endpoint
        for route in users.router.routes
        if route.path == path and method in route.methods
    )


def test_admin_can_create_person_name_username_without_changing_case(session_factory, monkeypatch):
    monkeypatch.setattr(users, "hash_password", lambda password: "encoded-password")
    response = _endpoint("/users", "POST")(
        users.UserCreateRequest(
            username="  Aguiar Júnior  ",
            email="aguiar@example.com",
            role="operator",
        ),
        _request(),
        ADMIN,
    )

    assert response["user"]["username"] == "Aguiar Júnior"
    with session_factory() as session:
        assert session.scalar(
            select(UserModel).where(UserModel.username == "Aguiar Júnior")
        ) is not None


def test_duplicate_usernames_are_allowed_for_different_accounts(session_factory, monkeypatch):
    monkeypatch.setattr(users, "hash_password", lambda password: "encoded-password")
    response = _endpoint("/users", "POST")(
        users.UserCreateRequest(
            username="admin",
            email="another-admin@example.com",
            role="operator",
        ),
        _request(),
        ADMIN,
    )

    assert response["user"]["username"] == "admin"


def test_usernames_reject_empty_and_whitespace_only_values():
    with pytest.raises(ValueError):
        users.UserCreateRequest(
            username="   ",
            email="empty@example.com",
            role="operator",
        )
    with pytest.raises(ValueError):
        users.UserUpdateRequest(username="   ")
    with pytest.raises(ValueError):
        users.UserCreateRequest(
            username="Aguiar\nJúnior",
            email="control@example.com",
            role="operator",
        )


def test_usernames_enforce_maximum_length():
    with pytest.raises(ValueError):
        users.UserCreateRequest(
            username="A" * 129,
            email="long@example.com",
            role="operator",
        )


def test_admin_can_rename_user_by_id_preserving_unicode_and_case(session_factory):
    response = _endpoint("/users/{user_id}", "PATCH")(
        OPERATOR.id,
        users.UserUpdateRequest(username="  Aguiar Júnior "),
        _request(),
        ADMIN,
    )

    assert response["user"]["username"] == "Aguiar Júnior"
    with session_factory() as session:
        assert session.get(UserModel, OPERATOR.id).username == "Aguiar Júnior"


def test_admin_can_change_email_and_email_is_normalized(session_factory):
    response = _endpoint("/users/{user_id}", "PATCH")(
        OPERATOR.id,
        users.UserUpdateRequest(email="  New.Operator@Example.COM "),
        _request(),
        ADMIN,
    )

    assert response["user"]["email"] == "new.operator@example.com"


def test_email_must_be_valid_and_unique(session_factory):
    with pytest.raises(ValueError):
        users.UserUpdateRequest(email="not-an-email")

    with pytest.raises(HTTPException) as error:
        _endpoint("/users/{user_id}", "PATCH")(
            OPERATOR.id,
            users.UserUpdateRequest(email="admin@observa.com"),
            _request(),
            ADMIN,
        )
    assert error.value.status_code == 409


def test_admin_can_create_user_with_normalized_email(session_factory, monkeypatch):
    monkeypatch.setattr(users, "hash_password", lambda password: "encoded-password")
    response = _endpoint("/users", "POST")(
        users.UserCreateRequest(
            username="new-user",
            email="  NEW-USER@Example.COM ",
            role="executor",
        ),
        _request(),
        ADMIN,
    )

    assert response["user"]["email"] == "new-user@example.com"
    with session_factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.username == "new-user"))
        assert user.email == "new-user@example.com"


def test_admin_cannot_create_duplicate_email(session_factory):
    with pytest.raises(HTTPException) as error:
        _endpoint("/users", "POST")(
            users.UserCreateRequest(
                username="another-operator",
                email=" ADMIN@OBSERVA.COM ",
                role="operator",
            ),
            _request(),
            ADMIN,
        )

    assert error.value.status_code == 409


def test_standard_development_users_have_expected_emails():
    assert DEVELOPMENT_USERS == (
        ("admin", "admin", "admin@observa.com", "DEV_ADMIN_PASSWORD"),
        ("operador", "operator", "operador@observa.com", "DEV_OPERATOR_PASSWORD"),
        ("executor", "executor", "executor@observa.com", "DEV_EXECUTOR_PASSWORD"),
    )


def test_login_uses_email_and_returns_display_username(monkeypatch):
    user = type(
        "User",
        (),
        {
            "id": 29,
            "username": "operador",
            "email": "operador@observa.com",
            "role": "operator",
            "is_active": True,
            "password_hash": "hashed",
        },
    )()

    class FakeSession:
        filter_clause = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def query(self, model):
            return self

        def filter(self, clause):
            self.filter_clause = str(clause)
            return self

        def first(self):
            assert "users.email" in self.filter_clause
            return user

        def commit(self):
            pass

    monkeypatch.setattr(clear, "SessionLocal", FakeSession)
    monkeypatch.setattr(clear, "verify_password", lambda password, hashed: True)
    create_token = Mock(return_value="token")
    monkeypatch.setattr(clear, "create_access_token", create_token)
    monkeypatch.setattr(clear.audit, "record_security_event", Mock())

    login_endpoint = next(
        route.endpoint
        for route in clear.router.routes
        if route.path == "/login" and "POST" in route.methods
    )
    response = login_endpoint(
        clear.LoginRequest(email=" Operador@Observa.com ", password="StrongPass1!"),
        _request(),
    )

    assert response["username"] == "operador"
    assert response["id"] == 29
    assert response["email"] == "operador@observa.com"
    create_token.assert_called_once_with(user_id=29, username="operador", role="operator")


def test_login_request_requires_a_valid_email():
    with pytest.raises(ValueError):
        clear.LoginRequest(email="not-an-email", password="anything")
    with pytest.raises(ValueError):
        clear.LoginRequest(username="admin", password="anything")


def test_user_rename_allows_duplicate_display_names(session_factory):
    response = _endpoint("/users/{user_id}", "PATCH")(
        OPERATOR.id,
        users.UserUpdateRequest(username="admin"),
        _request(),
        ADMIN,
    )

    assert response["user"]["username"] == "admin"


def test_password_policy_requires_each_rule():
    invalid_passwords = (
        ("abcdefg1!", "at least one uppercase letter"),
        ("ABCDEFG1!", "at least one lowercase letter"),
        ("Abcdefgh!", "at least one number"),
        ("Abcdefg12", "at least one special character"),
        ("Abc defg1", "at least one special character"),
        ("Ab1!", "at least 9 characters"),
    )

    for password, missing_requirement in invalid_passwords:
        assert missing_requirement in password_policy_errors(password)

    assert password_policy_errors("Abcdefg1!") == []


def test_generated_initial_password_meets_policy():
    assert password_policy_errors(generate_strong_password()) == []


def test_created_user_receives_a_strong_initial_password(session_factory, monkeypatch):
    monkeypatch.setattr(users, "hash_password", lambda password: "encoded-password-hash")

    response = _endpoint("/users", "POST")(
        users.UserCreateRequest(username="new-user", email="new-user@example.com", role="executor"),
        _request(),
        ADMIN,
    )

    assert password_policy_errors(response["initial_password"]) == []
    assert "initial_password" in response
    assert response["user"]["email"] == "new-user@example.com"
    with session_factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.username == "new-user"))
        assert user.password_hash == "encoded-password-hash"
        assert user.email == "new-user@example.com"


def test_admin_can_reset_password_without_returning_or_auditing_it(
    session_factory, monkeypatch
):
    stored_hashes = []
    monkeypatch.setattr(
        users,
        "hash_password",
        lambda password: stored_hashes.append(password) or "encoded-password-hash",
    )
    audit_record = Mock()
    monkeypatch.setattr(users.audit, "record_security_event", audit_record)

    response = _endpoint("/users/{user_id}/password", "PATCH")(
        OPERATOR.id,
        users.UserPasswordUpdateRequest(password="Abcdefg1!"),
        _request(),
        ADMIN,
    )

    assert response == {"message": "Password updated successfully"}
    assert "password" not in response
    assert stored_hashes == ["Abcdefg1!"]
    with session_factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.username == "operator"))
        assert user.password_hash == "encoded-password-hash"
    event = audit_record.call_args.kwargs
    assert event["action"] == "user.password.reset"
    assert event["actor_user_id"] == ADMIN.id
    assert "Abcdefg1!" not in repr(event)


def test_password_reset_rejects_weak_password(session_factory):
    with pytest.raises(HTTPException) as error:
        _endpoint("/users/{user_id}/password", "PATCH")(
            OPERATOR.id,
            users.UserPasswordUpdateRequest(password="weak"),
            _request(),
            ADMIN,
        )

    assert error.value.status_code == 422
    assert "at least 9 characters" in error.value.detail


def test_password_reset_endpoint_requires_admin_role():
    route = next(
        route
        for route in users.router.routes
        if route.path == "/users/{user_id}/password"
    )
    require_admin = route.dependant.dependencies[0].call

    with pytest.raises(HTTPException) as error:
        require_admin(OPERATOR)

    assert error.value.status_code == 403


def test_legacy_token_resolves_username_only_when_unambiguous(
    session_factory, monkeypatch
):
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda token: {"sub": "operator"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    assert dependencies.get_authenticated_user(_request(), credentials) == OPERATOR


def test_legacy_token_with_duplicate_username_is_rejected(
    session_factory, monkeypatch
):
    with session_factory() as session:
        session.add(
            UserModel(
                id=3,
                username="operator",
                email="another-operator@example.com",
                password_hash="hash",
                role="executor",
                is_active=True,
            )
        )
        session.commit()

    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda token: {"sub": "operator"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    with pytest.raises(HTTPException) as error:
        dependencies.get_authenticated_user(_request(), credentials)

    assert error.value.status_code == 401


def test_inactive_user_is_rejected_even_with_a_valid_token(
    session_factory, monkeypatch
):
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda token: {"uid": OPERATOR.id, "sub": "operator"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    assert dependencies.get_authenticated_user(_request(), credentials) == OPERATOR

    with session_factory() as session:
        user = session.get(UserModel, OPERATOR.id)
        user.is_active = False
        session.commit()

    with pytest.raises(HTTPException) as error:
        dependencies.get_authenticated_user(_request(), credentials)

    assert error.value.status_code == 401


def test_authentication_uses_stable_user_id_from_token(session_factory, monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda token: {"uid": OPERATOR.id, "sub": "old-username"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
    request = _request()

    principal = dependencies.get_authenticated_user(request, credentials)

    assert principal.id == OPERATOR.id
    assert principal.username == OPERATOR.username


def test_email_migration_assigns_standard_addresses_and_legacy_placeholders():
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20261029_0007_user_email.py"
    )
    spec = importlib.util.spec_from_file_location("user_email_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64) NOT NULL, "
                "password_hash VARCHAR(255) NOT NULL, role VARCHAR(16) NOT NULL, "
                "is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, username, password_hash, role, is_active, created_at) "
                "VALUES (1, 'admin', 'hash', 'admin', 1, CURRENT_TIMESTAMP), "
                "(2, 'operador', 'hash', 'operator', 1, CURRENT_TIMESTAMP), "
                "(3, 'executor', 'hash', 'executor', 1, CURRENT_TIMESTAMP), "
                "(4, 'custom-user', 'hash', 'executor', 1, CURRENT_TIMESTAMP)"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        addresses = connection.execute(
            text("SELECT username, email FROM users ORDER BY id")
        ).all()

    assert addresses == [
        ("admin", "admin@observa.com"),
        ("operador", "operador@observa.com"),
        ("executor", "executor@observa.com"),
        ("custom-user", "user-4@legacy.invalid"),
    ]
    engine.dispose()


def test_username_migration_removes_uniqueness_and_allows_long_names():
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "20261029_0008_display_names.py"
    )
    spec = importlib.util.spec_from_file_location("display_names_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(64) "
                "NOT NULL, email VARCHAR(254) NOT NULL, "
                "password_hash VARCHAR(255) NOT NULL, role VARCHAR(16) NOT NULL, "
                "is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL, "
                "CONSTRAINT uq_users_email UNIQUE (email), UNIQUE (username))"
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        constraints = inspect(connection).get_unique_constraints("users")
        assert {tuple(constraint["column_names"]) for constraint in constraints} == {
            ("email",)
        }
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, password_hash, role, is_active, created_at) "
                "VALUES (1, 'Aguiar Júnior', 'first@example.com', 'hash', 'admin', 1, CURRENT_TIMESTAMP), "
                "(2, 'Aguiar Júnior', 'second@example.com', 'hash', 'operator', 1, CURRENT_TIMESTAMP)"
            )
        )

    engine.dispose()
