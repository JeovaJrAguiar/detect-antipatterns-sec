# Observa Framework

## Database setup and migrations

The application schema is managed with Alembic. New databases are initialized by the container entrypoint before the API starts. For local execution, configure `DATABASE_URL` or all of `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_DB`, then run:

```sh
cd observa
pip install -r requirements.txt
alembic upgrade head
uvicorn observa.app:app --reload
```

See [MIGRATIONS.md](MIGRATIONS.md) for fresh database setup and the safe transition of an existing database previously created with `Base.metadata.create_all()`.
