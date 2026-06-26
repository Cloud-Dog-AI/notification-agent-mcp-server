#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: Database Manager for Notification Agent MCP Server - Handles database connections and initialization

Related Requirements: FR1.3, NF1.2
Related Tasks: T4
Related Architecture: CC6.1, DM1.1
Related Tests: UT1.2

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from src.utils.logger import get_logger
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Any, Dict, List, Sequence, Tuple

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError


def _is_locked_error(exc: BaseException) -> bool:
    """True when an exception is a transient SQLite 'database is locked' error."""
    msg = str(getattr(exc, "orig", exc)).lower()
    return "database is locked" in msg or "database table is locked" in msg


def _run_with_lock_retry(operation, *, max_seconds: float = 45.0, base_delay: float = 0.1):
    """Run a DB operation, retrying transient SQLite lock contention.

    req: FR-018 — the API server and the delivery worker write the same SQLite
    database concurrently. On filesystems where WAL shared-memory locking is
    unavailable (e.g. NFS), SQLite falls back to whole-DB rollback-journal locks
    whose acquisition is slow/unfair under high write volume, so a single
    statement can repeatedly lose the lock race and raise OperationalError
    "database is locked" before busy_timeout resolves it. Retry with capped
    exponential backoff, time-bounded, so transient contention yields a
    successful operation instead of a 500. No-op for non-locked errors and for
    PostgreSQL/local-disk-WAL deployments (which do not raise it).
    """
    last_exc: Optional[BaseException] = None
    delay = base_delay
    deadline = time.monotonic() + max_seconds
    while True:
        try:
            return operation()
        except OperationalError as exc:  # pragma: no cover - timing dependent
            if not _is_locked_error(exc):
                raise
            last_exc = exc
            if time.monotonic() >= deadline:
                break
            time.sleep(delay)
            delay = min(delay * 1.5, 1.5)
    raise last_exc

from cloud_dog_db import DatabaseSettings, build_sync_engine
from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

_fs = _PlatformLocalStorage(root_path="/")

logger = get_logger(__name__)


class _ExecuteResult:
    """Compatibility wrapper with cursor-like access for legacy tests."""

    def __init__(self, result, buffered_rows: Optional[Sequence[Any]] = None):
        self._buffered_rows = list(buffered_rows or [])
        self._row_index = 0
        self.lastrowid = getattr(result, "lastrowid", None) if result is not None else None
        self.rowcount = getattr(result, "rowcount", None) if result is not None else None

    def fetchone(self):
        if self._row_index >= len(self._buffered_rows):
            return None
        row = self._buffered_rows[self._row_index]
        self._row_index += 1
        return row

    def fetchall(self):
        if self._row_index >= len(self._buffered_rows):
            return []
        remaining = self._buffered_rows[self._row_index :]
        self._row_index = len(self._buffered_rows)
        return remaining


class _CompatConnection:
    """Provides minimal sqlite-style connection API used by legacy tests."""

    def __init__(self, manager: "DatabaseManager"):
        self._manager = manager

    def executescript(self, script: str):
        if not self._manager.engine and not self._manager.connect():
            raise RuntimeError("Database not connected")
        dialect = (self._manager.dialect or "").lower()
        if dialect in ("sqlite", "sqlite3"):
            with self._manager.engine.begin() as conn:
                conn.connection.executescript(script)
            return self

        statements = self._manager._split_sql_statements(script)
        with self._manager.engine.begin() as conn:
            for statement in statements:
                conn.exec_driver_sql(statement)
        return self

    def commit(self):
        return None

    def rollback(self):
        return None


class DatabaseManager:
    """Manages database connections and initialization"""

    def __init__(self, db_uri: str, logger_override: Optional[Any] = None):
        """Initialize database manager

        Args:
            db_uri: Database URI (e.g., sqlite3:///path/to/db.db, mysql://..., postgresql://...)
            logger_override: Optional logger override
        """
        self.logger = logger_override or logger
        self.db_uri = db_uri
        self.db_path: Optional[str] = None
        self.engine: Optional[Engine] = None
        self.dialect: str = ""
        self._lock = threading.RLock()
        self._compat_connection = _CompatConnection(self)

        # Normalize sqlite URI for SQLAlchemy and resolve db_path for tests.
        if db_uri.startswith("sqlite3://"):
            raw_path = db_uri.replace("sqlite3://", "", 1)
            if raw_path.startswith("/") and not raw_path.startswith("/opt") and not raw_path.startswith("/home") and not raw_path.startswith("/app"):
                raw_path = raw_path.lstrip("/")
            path = Path(raw_path)
            if not path.is_absolute():
                project_root = Path(__file__).parent.parent.parent
                path = project_root / path
            self.db_path = str(path)
            self.db_uri = f"sqlite:///{self.db_path}"
    
    def connect(self) -> bool:
        """Establish database connection"""
        with self._lock:
            if self.engine:
                return True

            # Ensure sqlite directory exists
            if self.db_path:
                _fs.create_dir(str(Path(self.db_path).parent), parents=True, exist_ok=True)

            try:
                settings = DatabaseSettings(url=self.db_uri)
                self.engine = build_sync_engine(settings)
                # req: FR-018 — SQLite is single-writer with whole-DB rollback-journal
                # locking, so the API server and the delivery worker writing the same
                # notify.db concurrently raise "database is locked". Enable WAL mode
                # (readers don't block the writer) and a generous busy_timeout so a
                # concurrent write waits for the lock instead of failing. PostgreSQL
                # deployments are unaffected (guarded on the sqlite dialect).
                if self.engine.dialect.name.startswith("sqlite"):
                    @event.listens_for(self.engine, "connect")
                    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
                        cursor = dbapi_connection.cursor()
                        try:
                            cursor.execute("PRAGMA journal_mode=WAL")
                            cursor.execute("PRAGMA busy_timeout=60000")
                            cursor.execute("PRAGMA synchronous=NORMAL")
                        finally:
                            cursor.close()
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self.dialect = self.engine.dialect.name
                return True
            except Exception as exc:
                self.logger.error(f"Failed to connect to database: {exc}")
                self.engine = None
                return False
    
    def disconnect(self):
        """Close database connection"""
        with self._lock:
            if self.engine:
                self.engine.dispose()
                self.engine = None

    @property
    def connection(self):
        """Legacy connection handle used in older test paths."""
        if not self.engine:
            if not self.connect():
                raise RuntimeError("Database not connected")
        return self._compat_connection
    
    def _prepare_query(self, query: str, params: Optional[Sequence[Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """Convert qmark placeholders to named params for SQLAlchemy."""
        if not params:
            return query, {}
        if isinstance(params, dict):
            return query, params
        if not isinstance(params, (list, tuple)):
            raise ValueError("params must be a dict, list, or tuple")
        if "?" not in query:
            return query, {f"p{i}": params[i] for i in range(len(params))}

        parts = query.split("?")
        expected = len(parts) - 1
        if expected != len(params):
            raise ValueError(f"Parameter count mismatch: {expected} placeholders, {len(params)} params")
        named = []
        for idx, part in enumerate(parts[:-1]):
            named.append(part)
            named.append(f":p{idx}")
        named.append(parts[-1])
        mapped = {f"p{i}": params[i] for i in range(len(params))}
        return "".join(named), mapped

    def execute(self, query: str, params: tuple = None):
        """Execute a query (INSERT/UPDATE/DELETE/DDL).

        Returns an object with lastrowid for compatibility.
        """
        with self._lock:
            if not self.engine:
                if not self.connect():
                    raise RuntimeError("Database not connected")

            sql, mapped = self._prepare_query(query, params)

            def _do():
                with self.engine.begin() as conn:
                    result = conn.execute(text(sql), mapped)
                    rows: Sequence[Any] = []
                    if getattr(result, "returns_rows", False):
                        rows = result.fetchall()
                    return _ExecuteResult(result, buffered_rows=rows)

            return _run_with_lock_retry(_do)
    
    def execute_many(self, query: str, params_list: list):
        """Execute a query with multiple parameter sets
        
        Args:
            query: SQL query
            params_list: List of parameter tuples
            
        Returns:
            Cursor object
        """
        with self._lock:
            if not self.engine:
                if not self.connect():
                    raise RuntimeError("Database not connected")

            if not params_list:
                return _ExecuteResult(None)

            sql, mapped = self._prepare_query(query, params_list[0])
            mapped_list = []
            for params in params_list:
                _, row = self._prepare_query(query, params)
                mapped_list.append(row)

            def _do_many():
                with self.engine.begin() as conn:
                    result = conn.execute(text(sql), mapped_list)
                    return _ExecuteResult(result)

            return _run_with_lock_retry(_do_many)
    
    def commit(self):
        """Commit current transaction"""
        # Transactions are committed per-statement via engine.begin()
        return None
    
    def rollback(self):
        """Rollback current transaction"""
        # Transactions are committed per-statement via engine.begin()
        return None
    
    def fetchone(self, query: str, params: tuple = None) -> Optional[dict]:
        """Fetch one row
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Row as dictionary or None
        """
        with self._lock:
            if not self.engine:
                if not self.connect():
                    raise RuntimeError("Database not connected")
            sql, mapped = self._prepare_query(query, params)

            def _do():
                with self.engine.connect() as conn:
                    result = conn.execute(text(sql), mapped)
                    row = result.mappings().first()
                    return dict(row) if row else None

            return _run_with_lock_retry(_do)
    
    def fetchall(self, query: str, params: tuple = None) -> list:
        """Fetch all rows
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of rows as dictionaries
        """
        with self._lock:
            if not self.engine:
                if not self.connect():
                    raise RuntimeError("Database not connected")
            sql, mapped = self._prepare_query(query, params)

            def _do():
                with self.engine.connect() as conn:
                    result = conn.execute(text(sql), mapped)
                    rows = result.mappings().all()
                    return [dict(row) for row in rows]

            return _run_with_lock_retry(_do)
    
    def initialize_schema(self):
        """Initialize database schema by running all migrations in order"""
        if not self.engine:
            if not self.connect():
                raise RuntimeError("Database not connected")

        migrations_dir = self._get_migrations_dir()
        if not _fs.exists(str(migrations_dir)):
            raise FileNotFoundError(f"Migrations directory not found: {migrations_dir}")

        migration_files = sorted(
            Path(e.path) for e in _fs.list_dir(str(migrations_dir))
            if not e.is_dir and e.path.endswith(".sql")
        )
        if not migration_files:
            raise FileNotFoundError(f"No migration files found in {migrations_dir}")

        for migration_file in migration_files:
            self.apply_migration_file(migration_file)
    
    def health_check(self) -> bool:
        """Check if database is accessible
        
        Returns:
            True if database is accessible, False otherwise
        """
        try:
            if not self.engine:
                if not self.connect():
                    return False
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def apply_migration_file(self, migration_file: Path) -> None:
        """Apply a single migration SQL file."""
        migration_sql = _fs.read_bytes(str(migration_file)).decode("utf-8")

        dialect = (self.dialect or "").lower()
        if dialect in ("sqlite", "sqlite3"):
            with self.engine.begin() as conn:
                try:
                    conn.connection.executescript(migration_sql)
                except SQLAlchemyError as exc:
                    if self._is_duplicate_error(exc):
                        self.logger.debug(f"⚠️  Migration {migration_file.name} already applied (skipping)")
                        return
                    self.logger.error(f"❌ Migration {migration_file.name} failed: {exc}")
                    raise
        else:
            statements = self._split_sql_statements(migration_sql)
            with self.engine.begin() as conn:
                for statement in statements:
                    try:
                        conn.exec_driver_sql(statement)
                    except SQLAlchemyError as exc:
                        if self._is_duplicate_error(exc):
                            self.logger.debug(f"⚠️  Migration {migration_file.name} already applied (skipping)")
                            continue
                        self.logger.error(f"❌ Migration {migration_file.name} failed: {exc}")
                        raise

        self.logger.info(f"✅ Migration {migration_file.name} applied successfully")

    def _split_sql_statements(self, sql: str) -> List[str]:
        """Split SQL script into statements, respecting quoted strings and comments."""
        statements: List[str] = []
        buf: List[str] = []
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
            # Prevents apostrophes in comments (e.g. "Provider's") from toggling
            # the in_single flag and breaking statement splitting.
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

    def _get_migrations_dir(self) -> Path:
        base_dir = Path(__file__).parent.parent.parent / "database" / "migrations"
        dialect = (self.dialect or "").lower()
        if dialect in ("mysql", "mariadb"):
            return base_dir / "mysql"
        if dialect in ("postgresql", "postgres"):
            return base_dir / "postgres"
        return base_dir

    def _is_duplicate_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "already exists",
                "duplicate column",
                "duplicate key name",
                "duplicate index",
                "duplicate entry",
            )
        )

    def get_dialect(self) -> str:
        return self.dialect
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions"""
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_uri: str = None) -> DatabaseManager:
    """Get or create global database manager
    
    Args:
        db_uri: Database URI (required on first call)
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    
    if _db_manager is None:
        if db_uri is None:
            raise ValueError("db_uri is required on first call")
        _db_manager = DatabaseManager(db_uri)
        _db_manager.connect()
    
    return _db_manager
