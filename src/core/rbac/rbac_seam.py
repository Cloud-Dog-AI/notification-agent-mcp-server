"""notification-agent resource-aware RBAC seam (W28A-744 / IDAM-B2 §4.2).

Adapts notification-agent's SQLite identity store to the W28A-741
``cloud_dog_idam`` 0.5.x resolver so the cascade RESOLVES live:

    user U --(group_members: U in G)--> group G
           --(rbac_bindings: group:G -> channel:P = channel.read)--> channel P

Three adapters, framework-free (no FastAPI import here):

- ``NotifMembershipResolver`` : ``cloud_dog_idam.rbac.membership.MembershipResolver``
  Protocol over ``GroupMemberRepository.get_user_groups``.
- ``NotifBindingRepository``  : the ``by_subject(subject_type, subject_id)`` data path
  over ``NotifBindingStore``.
- ``NotifResourceGuard``      : composes the shared ``RBACEngine`` + the two adapters
  and exposes ``authorise`` / ``allowed_resource_ids`` / ``is_admin`` / ``invalidate``.

The pure decision logic lives in ``cloud_dog_idam.rbac.grants`` (the W28A-741
keystone); this module only supplies the notification-specific membership +
binding data and a thin facade.
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

from typing import TYPE_CHECKING, Any, List

from cloud_dog_idam.rbac.grants import allowed_resource_ids, authorise

if TYPE_CHECKING:  # pragma: no cover
    from cloud_dog_idam import RBACEngine

    from src.core.rbac.binding_store import NotifBindingStore


class NotifMembershipResolver:
    """``MembershipResolver`` Protocol over the notification ``group_members`` table.

    ``groups_of(user_id)`` reads the live membership each call; the idam engine
    cache (``grants:{uid}``) handles caching and ``NotifResourceGuard.invalidate``
    drops it on add/remove-member so revocation lands within one request
    (cascade STEP 5).
    """

    def __init__(self, member_repo: Any) -> None:
        """Store the GroupMemberRepository (``get_user_groups``)."""
        self._member_repo = member_repo

    def groups_of(self, user_id: str) -> set[str]:
        """Return the set of group_id values ``user_id`` is currently a member of."""
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            return set()
        groups = self._member_repo.get_user_groups(uid) or []
        return {str(g["id"]) for g in groups if g.get("id") is not None}


class NotifBindingRepository:
    """``by_subject`` data path over the notification ``rbac_bindings`` store."""

    def __init__(self, store: "NotifBindingStore") -> None:
        """Store the NotifBindingStore facade."""
        self._store = store

    def by_subject(self, subject_type: str, subject_id: str) -> List[Any]:
        """Return binding rows for one subject (resolver data path)."""
        return self._store.by_subject(subject_type, subject_id)


class NotifResourceGuard:
    """Resource-aware authorisation facade for notification-agent (IDAM-B2 §3.1).

    Wraps the shared ``RBACEngine`` + the notification membership/binding adapters
    and routes decisions through the idam 0.5.x resolver. Default-DENY for
    resource-bearing checks; admin wildcard short-circuits; role-level flat
    permissions remain a fallback for surface gates (so the deployed flat
    ``admin``/``read-write``/``read-only`` roles keep working).
    """

    def __init__(self, engine: "RBACEngine", member_repo: Any, store: "NotifBindingStore") -> None:
        """Compose the engine with the notification membership + binding adapters."""
        self._engine = engine
        self._membership = NotifMembershipResolver(member_repo)
        self._binding_repo = NotifBindingRepository(store)

    def authorise(
        self,
        user_id: str,
        *,
        permission: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> bool:
        """Return whether ``user_id`` is authorised for ``(permission, resource_type, resource_id)``."""
        return authorise(
            str(user_id),
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            engine=self._engine,
            binding_repo=self._binding_repo,
            membership=self._membership,
        )

    def allowed_resource_ids(
        self, user_id: str, resource_type: str, permission: str
    ) -> set[str]:
        """Return the resource_id set the user may access (LIST filter; "*" = all)."""
        return allowed_resource_ids(
            str(user_id),
            resource_type,
            permission,
            engine=self._engine,
            binding_repo=self._binding_repo,
            membership=self._membership,
        )

    def is_admin(self, user_id: str) -> bool:
        """Return whether the principal holds the admin wildcard (for secret-masking)."""
        try:
            return "*" in set(self._engine.get_effective_permissions(str(user_id)))
        except Exception:
            return False

    def invalidate(self, *user_ids: str) -> None:
        """Drop cached grants for the given user(s) so cascade changes land live."""
        invalidator = getattr(self._engine, "_invalidate_user", None)
        for uid in user_ids:
            if callable(invalidator):
                try:
                    invalidator(str(uid))
                    continue
                except Exception:
                    pass
            cache = getattr(self._engine, "_cache", None)
            data = getattr(cache, "_data", None)
            if isinstance(data, dict):
                data.clear()


__all__ = ["NotifBindingRepository", "NotifMembershipResolver", "NotifResourceGuard"]
