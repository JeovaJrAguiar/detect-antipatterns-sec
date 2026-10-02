# Database migrations

Alembic owns the Observa database schema. Do not call `Base.metadata.create_all()` in application startup; schema changes belong in new files under `migrations/versions/` and are applied with `alembic upgrade head`.

## New database

Configure `DATABASE_URL`, or set `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_DB` (optionally `POSTGRES_PORT`, defaulting to `5432`). The application fails during import if neither a URL nor all required settings are provided. Start a new schema with:

```sh
cd observa
alembic upgrade head
```

The Docker image applies migrations before starting Uvicorn. Compose waits for PostgreSQL readiness before starting the Observa container.

## Existing database created with `create_all()`

The first migration represents the tables that `create_all()` already created; it is a baseline, not a migration that should create duplicate tables in an existing database.

1. Back up the database and stop all Observa application instances.
2. Confirm that `sources`, `detectors`, and `history` match the initial migration. Do not stamp a partial or differently structured schema.
3. For a matching existing schema, mark the baseline as applied:

   ```sh
   cd observa
   alembic stamp 20260928_0001
   ```

4. Start the application normally. Future schema revisions will then be applied by `alembic upgrade head`.

If the schema does not match the baseline, reconcile it with a reviewed, data-preserving migration before stamping. Do not drop tables or use `create_all()` to conceal a mismatch. Run the migration command once during deployment, not concurrently from multiple application workers.