# @pytest.mark.req("UC-015")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-108")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.ST
# @pytest.mark.internal
# @pytest.mark.req("CS-001")  # W28E-1807A: semantic binding (was probe; structural-conformance gate)
# PS-REQ-TEST-TRACE marker anchor for structural conformance.

"""T3-NA-CASCADE (resolver level) + T2-SECRET-MASK smoke — W28A-744 / IDAM-B2 §4.3.

Proves the group->channel cascade RESOLVES against the REAL ``NotifBindingStore``
(over an in-memory SQLite ``rbac_bindings`` table) + the REAL ``cloud_dog_idam``
0.5.x resolver via ``NotifResourceGuard``:

    restricted user U (no flat channel.read)  ->  add to group G
    (bound rbac_bindings group:G -> channel:P = channel.read)  ->  U reads P (allow),
    sees ONLY P (not Q), cannot WRITE P, cannot read Q  ->  remove U from G  ->  revoked.

The cascade is provable (not vacuous) precisely because U is ``restricted`` — its
access to P comes ONLY through the group binding, never a flat role grant. This is
the resolver-level proof; the live API/MCP/A2A/WebUI proof is the e2e T3-NA-CASCADE.

Run: PYTHONPATH=<worktree>:<worktree>/src:<platform-standards>/packages/backend/platform-idam \\
     python3 -m pytest tests/smoke/test_cascade_resolves.py -v
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

import sqlite3

import pytest

from cloud_dog_idam import RBACEngine, mask_secrets

from src.core.rbac.binding_store import NotifBindingStore
from src.core.rbac.rbac_seam import NotifResourceGuard

pytestmark = [
    pytest.mark.unit,
    pytest.mark.non_llm,
    pytest.mark.no_llm_dependency,
    pytest.mark.no_runtime_dependency,
]

CHANNEL = "channel"
READ = "channel.read"
WRITE = "channel.write"

ADMIN_ID = "1"
U_ID = "3"          # restricted GROUPUSER
G_ID = "7"          # group G
P_ID = "11"         # channel P (bound to G)
Q_ID = "22"         # channel Q (unbound)


class _MemDB:
    """Minimal DatabaseManager-shaped adapter over an in-memory sqlite3 connection."""

    def __init__(self) -> None:
        self._con = sqlite3.connect(":memory:")
        self._con.row_factory = sqlite3.Row
        self._con.execute(
            "CREATE TABLE rbac_bindings ("
            "binding_id TEXT PRIMARY KEY, subject_type TEXT, subject_id TEXT, project TEXT, "
            "resource_type TEXT, resource_id TEXT, permission TEXT, granted_by TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )

    def execute(self, sql, params=()):
        return self._con.execute(sql, params)

    def fetchone(self, sql, params=()):
        return self._con.execute(sql, params).fetchone()

    def fetchall(self, sql, params=()):
        return self._con.execute(sql, params).fetchall()

    def commit(self):
        self._con.commit()


class _FakeMemberRepo:
    """In-memory ``get_user_groups`` matching GroupMemberRepository's contract."""

    def __init__(self) -> None:
        self._members: dict[int, set[int]] = {}

    def add(self, group_id: int, user_id: int) -> None:
        self._members.setdefault(user_id, set()).add(group_id)

    def remove(self, group_id: int, user_id: int) -> None:
        self._members.get(user_id, set()).discard(group_id)

    def get_user_groups(self, user_id: int):
        return [{"id": gid} for gid in sorted(self._members.get(int(user_id), set()))]


def _build():
    db = _MemDB()
    store = NotifBindingStore(db)
    members = _FakeMemberRepo()
    # Flat roles: admin -> *, read-write -> read+write, read-only -> read, restricted -> none.
    engine = RBACEngine(role_permissions={
        "admin": {"*"},
        "read-write": {READ, WRITE},
        "read-only": {READ},
        "restricted": set(),
    })
    engine.assign_role_to_user(ADMIN_ID, "admin")
    engine.assign_role_to_user(U_ID, "restricted")
    # The group->resource binding: G may READ channel P (NOT Q, NOT write).
    store.create_binding({
        "subject_type": "group", "subject_id": G_ID,
        "resource_type": CHANNEL, "resource_id": P_ID,
        "permission": READ, "granted_by": "admin",
    })
    guard = NotifResourceGuard(engine, members, store)
    return guard, members


def test_cascade_resolves_add_then_revoke():
    """T3-NA-CASCADE: add-to-group grants P-read; remove revokes; scoped + graded."""
    guard, members = _build()

    # STEP 1 — baseline: U not in G -> default-DENY on P.
    assert guard.authorise(U_ID, permission=READ, resource_type=CHANNEL, resource_id=P_ID) is False

    # STEP 2 — group-admin adds U to G (the grant).
    members.add(int(G_ID), int(U_ID))
    guard.invalidate(U_ID)

    # STEP 3 — CASCADE ON: U reads P, sees ONLY P, cannot write P, cannot read Q.
    assert guard.authorise(U_ID, permission=READ, resource_type=CHANNEL, resource_id=P_ID) is True
    assert guard.allowed_resource_ids(U_ID, CHANNEL, READ) == {P_ID}
    assert guard.authorise(U_ID, permission=WRITE, resource_type=CHANNEL, resource_id=P_ID) is False
    assert guard.authorise(U_ID, permission=READ, resource_type=CHANNEL, resource_id=Q_ID) is False

    # STEP 4 — group-admin removes U from G (the revoke).
    members.remove(int(G_ID), int(U_ID))
    guard.invalidate(U_ID)

    # STEP 5 — CASCADE OFF (live, no restart): P-read denied again.
    assert guard.authorise(U_ID, permission=READ, resource_type=CHANNEL, resource_id=P_ID) is False
    assert guard.allowed_resource_ids(U_ID, CHANNEL, READ) == set()


def test_admin_and_flat_roles_see_all():
    """Admin (flat '*') and read-only (flat channel.read) list all channels (allowed = {'*'})."""
    guard, _ = _build()
    assert guard.is_admin(ADMIN_ID) is True
    assert guard.authorise(ADMIN_ID, permission=READ, resource_type=CHANNEL, resource_id=Q_ID) is True
    assert guard.allowed_resource_ids(ADMIN_ID, CHANNEL, READ) == {"*"}


def test_secret_masking_non_admin_vs_admin():
    """T2-SECRET-MASK: channel config secret masked for non-admin, cleartext for admin."""
    guard, _ = _build()
    payload = {"endpoint": "https://example", "auth": {"password": "s3cr3t-P", "user": "ops"}}

    masked = mask_secrets(payload, is_admin=guard.is_admin(U_ID))
    assert masked["auth"]["password"] == "***REDACTED***"
    assert masked["auth"]["user"] == "ops"  # non-secret preserved

    revealed = mask_secrets(payload, is_admin=guard.is_admin(ADMIN_ID))
    assert revealed["auth"]["password"] == "s3cr3t-P"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
