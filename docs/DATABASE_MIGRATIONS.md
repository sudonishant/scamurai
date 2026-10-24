# Database migrations

Scamurai database schema is managed by Alembic. The API does not create or alter tables during application startup.

## Apply schema changes

For a local database configured through `SCAMURAI_DATABASE_URL` (or `backend/.env`), run this from the repository root:

```bash
make db-upgrade
```

The equivalent command is `cd backend && alembic upgrade head`. Docker Compose runs a one-shot `migrate` service and waits for it to finish before starting the API and worker. Migration errors stop deployment rather than leaving the app to serve against a partial schema.

Review new generated revisions before release. Check table and column definitions, foreign keys and delete behavior, indexes, unique constraints, and both `upgrade()` and `downgrade()`. Back up production data before applying revisions; downgrades can remove data.

## Existing unversioned databases

Databases created by older app versions with `Base.metadata.create_all()` have no Alembic revision marker. Before Compose runs migrations against an existing database, first take a verified backup and compare its full schema with the initial revision; do not run the initial revision against that database as though it were empty, and do not automatically stamp it. Only when every table, column, index, and constraint matches that revision may an operator perform the one-time stamp to mark it as already at the initial revision:

```bash
cd backend
alembic stamp f8057024479a
alembic current
```

If the schema differs, prepare and review a data-preserving migration instead. Never stamp an unverified database: Alembic would skip the missing schema work.
