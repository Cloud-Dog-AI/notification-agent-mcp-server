# Database Directory

This directory contains the SQLite database files and migration scripts for the Notification Agent MCP Server.

## Structure

- `migrations/` - SQL migration scripts
- `notify.db` - Main application database (created automatically)
- `test.db` - Test database (used during testing)

## Migrations

Migrations are applied automatically on server startup. To manually run migrations:

```bash
python scripts/migrate_database.py
```

## Admin Credentials

The initial schema does not create an admin user. Configure an admin account via env/config.

## Database Schema

See `migrations/001_initial_schema.sql` for the complete schema definition.

### Key Tables

- **messages** - Notification requests
- **deliveries** - Per-channel delivery tracking
- **receipts** - Provider confirmation callbacks
- **channels** - Channel configurations
- **users** - Admin users
- **templates** - Content templates
- **audit_events** - Security audit log

## Backup

To backup the database:

```bash
cp database/notify.db database/notify.db.backup
```

## Reset Database

⚠️ **WARNING**: This will destroy all data!

```bash
make db-reset
```

