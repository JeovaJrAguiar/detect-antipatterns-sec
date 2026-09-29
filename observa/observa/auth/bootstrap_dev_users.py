import os

from sqlalchemy import select

from observa.auth.security import hash_password, verify_password
from observa.database.database import SessionLocal
from observa.database.models import UserModel


DEVELOPMENT_USERS = (
    ("admin", "admin", "DEV_ADMIN_PASSWORD"),
    ("operador", "operator", "DEV_OPERATOR_PASSWORD"),
    ("executor", "executor", "DEV_EXECUTOR_PASSWORD"),
)


def main() -> None:
    if os.getenv("APP_ENV") != "development":
        raise SystemExit("Development users can only be bootstrapped in APP_ENV=development")

    accounts = []
    for username, role, password_key in DEVELOPMENT_USERS:
        password = os.getenv(password_key, "")
        if len(password) < 12:
            raise SystemExit(f"{password_key} must contain at least 12 characters")
        accounts.append((username, role, password))

    with SessionLocal() as session:
        existing_users = {
            user.username: user
            for user in session.scalars(
                select(UserModel).where(
                    UserModel.username.in_([account[0] for account in accounts])
                )
            )
        }

        for username, role, password in accounts:
            existing_user = existing_users.get(username)
            if existing_user is not None and (
                existing_user.role != role
                or not existing_user.is_active
                or not verify_password(password, existing_user.password_hash)
            ):
                raise SystemExit(
                    f"Credentials for '{username}' do not match the active database account. "
                    "Restore the original observa/.env; no user accounts were changed."
                )

        created_users = []
        for username, role, password in accounts:
            if username not in existing_users:
                session.add(
                    UserModel(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                        is_active=True,
                    )
                )
                created_users.append(username)

        session.commit()

    if created_users:
        print("Created development users: " + ", ".join(created_users))
    else:
        print("All development users already exist; passwords and accounts were preserved.")


if __name__ == "__main__":
    main()