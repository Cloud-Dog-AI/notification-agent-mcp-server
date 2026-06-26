"""notification-agent cloud_dog_db baseline

Revision ID: 20260306_0001
Revises:
Create Date: 2026-03-06 00:00:00
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260306_0001"
down_revision = None
branch_labels = None
depends_on = None


_SQLITE_FILES = [
    "001_initial_schema.sql",
    "002_add_message_guid.sql",
    "002_user_management_personalization.sql",
    "003_notification_storage_and_media.sql",
    "004_add_delivery_metadata_json.sql",
]

_MYSQL_FILES = [
    "mysql/001_initial_schema.sql",
    "mysql/002_add_message_guid.sql",
    "mysql/002_user_management_personalization.sql",
    "mysql/003_notification_storage_and_media.sql",
    "mysql/004_add_delivery_metadata_json.sql",
    "mysql/005_expand_provider_tracking_id.sql",
]

_POSTGRES_FILES = [
    "postgres/001_initial_schema.sql",
    "postgres/002_add_message_guid.sql",
    "postgres/002_user_management_personalization.sql",
    "postgres/003_notification_storage_and_media.sql",
    "postgres/004_add_delivery_metadata_json.sql",
    "postgres/005_expand_provider_tracking_id.sql",
]


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escape_next = False

    idx = 0
    length = len(sql)
    while idx < length:
        char = sql[idx]
        next_char = sql[idx + 1] if idx + 1 < length else ""

        if escape_next:
            buf.append(char)
            escape_next = False
            idx += 1
            continue

        if char == "\\":
            buf.append(char)
            escape_next = True
            idx += 1
            continue

        # Skip SQL line comments (-- to end of line) when not inside a string.
        # This prevents apostrophes in comments (e.g. "Provider's") from
        # toggling the in_single flag and breaking statement splitting.
        if char == "-" and next_char == "-" and not in_single and not in_double:
            newline = sql.find("\n", idx)
            if newline == -1:
                buf.append(sql[idx:])
                break
            buf.append(sql[idx:newline])
            idx = newline
            continue

        if char == "'" and not in_double:
            if in_single and next_char == "'":
                buf.append("''")
                idx += 2
                continue
            in_single = not in_single
            buf.append(char)
            idx += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            buf.append(char)
            idx += 1
            continue

        if char == ";" and not in_single and not in_double:
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            idx += 1
            continue

        buf.append(char)
        idx += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)

    return statements


def _apply_sql_script(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    bind = op.get_bind()
    for statement in _split_sql_statements(sql):
        # Use exec_driver_sql to avoid SQLAlchemy text() interpreting
        # JSON content like :null as bind parameters (cd3x error).
        bind.exec_driver_sql(statement)


def upgrade() -> None:
    migration_root = Path(__file__).resolve().parents[2]
    bind = op.get_bind()
    dialect = bind.dialect.name.lower()

    if dialect in {"mysql", "mariadb"}:
        files = _MYSQL_FILES
    elif dialect in {"postgres", "postgresql"}:
        files = _POSTGRES_FILES
    else:
        files = _SQLITE_FILES

    for rel in files:
        _apply_sql_script(migration_root / rel)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name.lower()
    cascade = " CASCADE" if dialect in {"postgres", "postgresql"} else ""

    tables = [
        "notification_storage",
        "media_files",
        "receipts",
        "deliveries",
        "llm_prompts",
        "group_keywords",
        "group_members",
        "user_keywords",
        "user_destinations",
        "ldap_syncs",
        "templates",
        "audit_events",
        "groups",
        "users",
        "channels",
        "messages",
    ]
    for table in tables:
        bind.exec_driver_sql(f"DROP TABLE IF EXISTS {table}{cascade}")
