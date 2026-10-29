from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from observa.auth import bootstrap_admin, bootstrap_dev_users
from observa.database.models import UserModel


def test_bootstrap_finds_standard_account_by_email_and_preserves_custom_name(
    monkeypatch, capsys
):
    engine = create_engine("sqlite://")
    UserModel.__table__.create(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(bootstrap_dev_users, "SessionLocal", factory)
    monkeypatch.setattr(bootstrap_dev_users, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(bootstrap_dev_users, "hash_password", lambda password: "new-hash")
    monkeypatch.setenv("APP_ENV", "development")
    for _, _, _, password_key in bootstrap_dev_users.DEVELOPMENT_USERS:
        monkeypatch.setenv(password_key, "StrongLocalPassword123!")

    with factory() as session:
        session.add(
            UserModel(
                username="Aguiar Júnior",
                email="admin@observa.com",
                password_hash="existing-hash",
                role="admin",
                is_active=True,
            )
        )
        session.commit()

    bootstrap_dev_users.main()

    with factory() as session:
        admin = session.scalar(
            select(UserModel).where(UserModel.email == "admin@observa.com")
        )
        assert admin.username == "Aguiar Júnior"
        assert admin.password_hash == "existing-hash"
        assert session.scalar(
            select(UserModel).where(UserModel.username == "admin")
        ) is None

    assert "Created development users" in capsys.readouterr().out
    engine.dispose()


def test_admin_bootstrap_finds_account_by_email_and_preserves_custom_name(monkeypatch):
    engine = create_engine("sqlite://")
    UserModel.__table__.create(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(bootstrap_admin, "SessionLocal", factory)
    monkeypatch.setattr(bootstrap_admin, "hash_password", lambda password: "new-hash")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "StrongLocalPassword123!")

    with factory() as session:
        session.add(
            UserModel(
                username="Aguiar Júnior",
                email="admin@example.com",
                password_hash="existing-hash",
                role="admin",
                is_active=True,
            )
        )
        session.commit()

    bootstrap_admin.main()

    with factory() as session:
        admin = session.scalar(
            select(UserModel).where(UserModel.email == "admin@example.com")
        )
        assert admin.username == "Aguiar Júnior"
        assert admin.password_hash == "existing-hash"
        assert len(session.scalars(select(UserModel)).all()) == 1

    engine.dispose()
