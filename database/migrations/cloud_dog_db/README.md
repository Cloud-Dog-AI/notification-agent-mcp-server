# notification-agent cloud_dog_db migrations

This directory hosts Alembic migrations executed via `cloud_dog_db.migrations.runner`.

The baseline revision replays the existing SQL migration chain per dialect:
- SQLite: `database/migrations/*.sql`
- MySQL: `database/migrations/mysql/*.sql`
- PostgreSQL: `database/migrations/postgres/*.sql`
