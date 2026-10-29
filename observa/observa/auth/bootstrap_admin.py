import os

from sqlalchemy import select

from observa.auth.security import hash_password, normalize_email
from observa.database.database import SessionLocal
from observa.database.models import UserModel


def main() -> None:
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip().lower()
    raw_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not username or not raw_email or not password:
        raise SystemExit(
            "Set BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_EMAIL, "
            "and BOOTSTRAP_ADMIN_PASSWORD explicitly"
        )
    try:
        email = normalize_email(raw_email)
    except ValueError as error:
        raise SystemExit("BOOTSTRAP_ADMIN_EMAIL must be a valid email address") from error
    if len(password) < 12:
        raise SystemExit("The bootstrap admin password must contain at least 12 characters")

    with SessionLocal() as session:
        existing_admin = session.scalar(
            select(UserModel).where(UserModel.username == username)
        )
        if existing_admin is not None:
            if existing_admin.role != "admin" or not existing_admin.is_active:
                raise SystemExit("The configured bootstrap account exists but is not an active admin")
            print(f"Admin '{username}' ja existe; senha e conta foram preservadas.")
            return

        session.add(
            UserModel(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )
        )
        session.commit()

    print(f"Admin '{username}' criado.")


if __name__ == "__main__":
    main()