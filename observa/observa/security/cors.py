from urllib.parse import urlsplit


def parse_allowed_origins(raw_origins: str) -> list[str]:
    origins = []
    for entry in raw_origins.split(","):
        candidate = entry.strip()
        if not candidate:
            continue

        try:
            parsed = urlsplit(candidate)
            parsed.port
        except ValueError as exc:
            raise ValueError(
                "OBSERVA_CORS_ORIGINS must contain explicit origins using HTTP or HTTPS."
            ) from exc

        if (
            "*" in candidate
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OBSERVA_CORS_ORIGINS must contain explicit origins using HTTP or HTTPS."
            )

        origins.append(f"{parsed.scheme}://{parsed.netloc}")

    return list(dict.fromkeys(origins))