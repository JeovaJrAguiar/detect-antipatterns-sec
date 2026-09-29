# Observa Framework

## Database setup and migrations

The application schema is managed with Alembic. New databases are initialized by the container entrypoint before the API starts. Set `JWT_SECRET_KEY` to at least 32 characters in addition to configuring `DATABASE_URL` or all of `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_DB`, then run locally:

```sh
cd observa
pip install -r requirements.txt
alembic upgrade head
uvicorn observa.app:app --reload
```

See [MIGRATIONS.md](MIGRATIONS.md) for fresh database setup and the safe transition of an existing database previously created with `Base.metadata.create_all()`.

## Initial administrator

Create the first administrator explicitly after applying migrations. The command requires a username and a password with at least 12 characters and never resets an existing account:

```sh
BOOTSTRAP_ADMIN_USERNAME=admin BOOTSTRAP_ADMIN_PASSWORD='use-a-local-secret' python -m observa.auth.bootstrap_admin
```

The development script creates a local-only `observa/.env` containing a generated JWT signing key and separate passwords for the Admin, Operador, and Executor accounts, then bootstraps any missing accounts without replacing existing passwords. This file is excluded from the Docker build context and Git.
