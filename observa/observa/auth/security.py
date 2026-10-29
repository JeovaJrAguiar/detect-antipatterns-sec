import os
import re
import secrets
import string
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")

ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
PASSWORD_HASHER = PasswordHash.recommended()
PASSWORD_REQUIREMENT_LABELS = {
    "length": "at least 9 characters",
    "uppercase": "at least one uppercase letter",
    "lowercase": "at least one lowercase letter",
    "number": "at least one number",
    "special": "at least one special character",
}


def password_requirements(password: str) -> dict[str, bool]:
    return {
        "length": len(password) >= 9,
        "uppercase": re.search(r"[A-Z]", password) is not None,
        "lowercase": re.search(r"[a-z]", password) is not None,
        "number": re.search(r"[0-9]", password) is not None,
        "special": re.search(r"[^A-Za-z0-9\s]", password) is not None,
    }


def password_policy_errors(password: str) -> list[str]:
    return [
        PASSWORD_REQUIREMENT_LABELS[requirement]
        for requirement, is_satisfied in password_requirements(password).items()
        if not is_satisfied
    ]


def normalize_email(email: str) -> str:
    normalized_email = email.strip().lower()
    if (
        len(normalized_email) < 6
        or len(normalized_email) > 254
        or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email) is None
    ):
        raise ValueError("A valid email address is required")
    return normalized_email


def generate_strong_password() -> str:
    characters = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation),
    ]
    alphabet = string.ascii_letters + string.digits + string.punctuation
    characters.extend(secrets.choice(alphabet) for _ in range(12))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, username: str, role: str) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "uid": user_id,
        "role": role,
        "iat": issued_at,
        "exp": issued_at + ACCESS_TOKEN_LIFETIME,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])