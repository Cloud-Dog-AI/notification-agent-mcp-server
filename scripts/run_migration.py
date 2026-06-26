#!/usr/bin/env python3
"""
Run database migration script
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_manager import ConfigManager
from src.database.db_manager import DatabaseManager


def run_migration(migration_file: Path, db_uri: str) -> bool:
    """Run a migration file against the database."""
    print(f"Running migration: {migration_file.name}")
    db = DatabaseManager(db_uri)
    if not db.connect():
        print("❌ Failed to connect to database")
        return False
    db.apply_migration_file(migration_file)
    return True


def _resolve_db_uri(env_file: str, override_uri: str) -> str:
    if override_uri:
        return override_uri
    if not env_file:
        raise RuntimeError("Missing --env or --db-uri")
    config = ConfigManager(env_file=env_file, load_env_file=True)
    db_uri = config.get("db.uri")
    if not db_uri:
        raise RuntimeError("Missing required configuration: db.uri")
    return db_uri


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single migration file.")
    parser.add_argument("--env", dest="env_file", required=False, help="Env file to load (e.g., private/env-test)")
    parser.add_argument("--db-uri", dest="db_uri", required=False, help="Database URI override")
    parser.add_argument("--file", dest="migration_file", required=False, help="Migration file path")
    args = parser.parse_args()

    migration_file = Path(args.migration_file) if args.migration_file else (
        Path(__file__).parent.parent / "database" / "migrations" / "002_user_management_personalization.sql"
    )
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    try:
        db_uri = _resolve_db_uri(args.env_file, args.db_uri)
    except RuntimeError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    success = run_migration(migration_file, db_uri)
    sys.exit(0 if success else 1)

