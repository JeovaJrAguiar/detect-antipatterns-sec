# Observa Framework

## Database setup and migrations

The application schema is managed with Alembic. New databases are initialized by the container entrypoint before the API starts. Set `JWT_SECRET_KEY` to at least 32 characters in addition to configuring `DATABASE_URL` or all of `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_DB`, then run locally:

```sh
cd observa
pip install -r requirements.txt
alembic upgrade head
uvicorn observa.app:app --reload
```

For a frontend hosted on a different origin, set `OBSERVA_CORS_ORIGINS` to a comma-separated list of exact HTTP or HTTPS origins, such as `http://localhost:3000,https://app.example.com`. Leave it empty to deny cross-origin browser access. Wildcards and URL paths are rejected.

## Rate limiting

Rate limits use in-process memory and are therefore enforced independently by each API worker. HTTP limits are keyed by the connecting client IP; forwarded IP headers are not trusted. Remote source and detector calls share a separate per-host limit. Requests rejected by an HTTP limit receive `429` and `Retry-After`.

Set `APP_ENV=development` to use the more permissive local defaults. All values can be overridden with `<count>/<second|minute|hour|day>`:

| Variable | Protected operation | Development default | Other environments |
|---|---|---:|---:|
| `OBSERVA_RATE_LIMIT_LOGIN` | Login per client IP | `30/minute` | `5/minute` |
| `OBSERVA_RATE_LIMIT_USER_CREATE` | User creation per client IP | `60/hour` | `5/hour` |
| `OBSERVA_RATE_LIMIT_RUN` | Execute, autorun, and collect per client IP | `120/minute` | `20/minute` |
| `OBSERVA_RATE_LIMIT_REMOTE` | Outbound calls per destination host | `120/minute` | `30/minute` |

These process-local limits are an application-level guard, not a substitute for shared limits at an ingress when deploying multiple workers or replicas.

See [MIGRATIONS.md](MIGRATIONS.md) for fresh database setup and the safe transition of an existing database previously created with `Base.metadata.create_all()`.

## Initial administrator

Create the first administrator explicitly after applying migrations. The command requires a username and a password with at least 12 characters and never resets an existing account:

```sh
BOOTSTRAP_ADMIN_USERNAME=admin BOOTSTRAP_ADMIN_PASSWORD='use-a-local-secret' python -m observa.auth.bootstrap_admin
```

The development script creates a local-only `observa/.env` containing a generated JWT signing key and separate passwords for the Admin, Operador, and Executor accounts, then bootstraps any missing accounts without replacing existing passwords. This file is excluded from the Docker build context and Git. Users created by an Admin receive a generated initial password, shown only in the creation response, and can use it to log in immediately.
