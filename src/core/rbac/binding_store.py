"""DB-backed RBAC binding store — W28A-744 / IDAM-B2 §2.1.

The group->resource binding rows (the cascade's data path) persisted in the
notification-agent SQLite DB ``rbac_bindings`` table. Consumed at authorisation
time by ``NotifBindingRepository.by_subject`` feeding the ``cloud_dog_idam``
0.5.x resolver (``cloud_dog_idam.rbac.grants.authorise``). No domain-table
schema change (IDAM-B2 §2): channels are never FK-bound; the binding is the join.
"""

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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class RBACBindingRecord:
    """One group/user -> resource grant. Carries exactly the attributes the
    ``cloud_dog_idam`` resolver reads (``resource_type``/``resource_id``/``permission``)."""

    binding_id: str
    subject_type: str
    subject_id: str
    project: str
    resource_type: str
    resource_id: str
    permission: str
    granted_by: str

    def to_dict(self) -> Dict[str, Any]:
        """Return the API/WebUI response shape."""
        return {
            "binding_id": self.binding_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "project": self.project,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "permission": self.permission,
            "granted_by": self.granted_by,
        }


def _row_to_record(row: Any) -> RBACBindingRecord:
    """Map a DB row (dict or sqlite Row) to a binding record."""
    d = dict(row)
    return RBACBindingRecord(
        binding_id=str(d["binding_id"]),
        subject_type=str(d["subject_type"]),
        subject_id=str(d["subject_id"]),
        project=str(d.get("project") or "notification-agent"),
        resource_type=str(d["resource_type"]),
        resource_id=str(d.get("resource_id") or "*"),
        permission=str(d["permission"]),
        granted_by=str(d.get("granted_by") or "system"),
    )


class NotifBindingStore:
    """RBAC binding persistence over the notification DB ``rbac_bindings`` table."""

    def __init__(self, db: Any) -> None:
        """Store the DatabaseManager (``execute``/``fetchone``/``fetchall``/``commit``)."""
        self._db = db

    def list_bindings(self) -> List[RBACBindingRecord]:
        """Return all bindings sorted by subject then resource."""
        rows = self._db.fetchall(
            "SELECT * FROM rbac_bindings ORDER BY subject_type, subject_id, resource_type, resource_id"
        ) or []
        return [_row_to_record(r) for r in rows]

    def by_subject(self, subject_type: str, subject_id: str) -> List[RBACBindingRecord]:
        """Return bindings for one subject — the resolver's ``by_subject`` data path."""
        rows = self._db.fetchall(
            "SELECT * FROM rbac_bindings WHERE subject_type = ? AND subject_id = ?",
            (str(subject_type), str(subject_id)),
        ) or []
        return [_row_to_record(r) for r in rows]

    def get_binding(self, binding_id: str) -> Optional[RBACBindingRecord]:
        """Return one binding by id, or None."""
        row = self._db.fetchone(
            "SELECT * FROM rbac_bindings WHERE binding_id = ?", (str(binding_id),)
        )
        return _row_to_record(row) if row else None

    def create_binding(self, payload: Dict[str, Any]) -> RBACBindingRecord:
        """Create one binding from a validated payload."""
        record = RBACBindingRecord(
            binding_id=str(payload.get("binding_id") or uuid4().hex),
            subject_type=str(payload.get("subject_type", "group")),
            subject_id=str(payload.get("subject_id", "")),
            project=str(payload.get("project") or "notification-agent"),
            resource_type=str(payload.get("resource_type", "channel")),
            resource_id=str(payload.get("resource_id") or "*"),
            permission=str(payload.get("permission", "channel.read")),
            granted_by=str(payload.get("granted_by") or "system"),
        )
        self._db.execute(
            "INSERT INTO rbac_bindings "
            "(binding_id, subject_type, subject_id, project, resource_type, resource_id, permission, granted_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.binding_id, record.subject_type, record.subject_id, record.project,
                record.resource_type, record.resource_id, record.permission, record.granted_by,
            ),
        )
        self._db.commit()
        return record

    def delete_binding(self, binding_id: str) -> bool:
        """Delete (revoke) one binding by id. Returns whether it existed."""
        existed = self.get_binding(binding_id) is not None
        self._db.execute("DELETE FROM rbac_bindings WHERE binding_id = ?", (str(binding_id),))
        self._db.commit()
        return existed


_RBAC_BINDINGS_DDL = (
    "CREATE TABLE IF NOT EXISTS rbac_bindings ("
    "binding_id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, "
    "project TEXT NOT NULL DEFAULT 'notification-agent', resource_type TEXT NOT NULL, "
    "resource_id TEXT NOT NULL DEFAULT '*', permission TEXT NOT NULL, "
    "granted_by TEXT NOT NULL DEFAULT 'system', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
    "CREATE INDEX IF NOT EXISTS idx_rbac_bindings_subject ON rbac_bindings (subject_type, subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_rbac_bindings_resource ON rbac_bindings (resource_type, resource_id)",
)


def ensure_rbac_bindings_table(db: Any) -> None:
    """Idempotently ensure the rbac_bindings table exists at startup.

    Migration 008 creates it for fresh DBs, but ``initialize_schema`` only runs on
    first-init — existing deployment DBs predating 008 would otherwise lack the table.
    Mirrors ``ensure_role_tables``: CREATE ... IF NOT EXISTS, safe on every startup.
    """
    for stmt in _RBAC_BINDINGS_DDL:
        db.execute(stmt)
    db.commit()


__all__ = ["NotifBindingStore", "RBACBindingRecord", "ensure_rbac_bindings_table"]
