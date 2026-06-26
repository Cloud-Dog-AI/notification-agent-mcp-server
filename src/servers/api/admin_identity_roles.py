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
Description: Admin Roles CRUD service backed by the canonical cloud_dog_idam
            SqlAlchemyRoleStore (PS-71 IW3A). Serves the persistent role
            definitions consumed by the WebUI Roles page via
            /api/v1/admin/roles. Modelled on the proven file-mcp recipe
            (file_mcp_server/admin_identity.py role methods).

Related Requirements: CS1.1, FR1.14
Related Tasks: W28A-876
Related Architecture: SE1.1
Related Tests: IT-roles (focused integration probe)

Recent Changes (max 10):
- 2026-06-07: Initial roles admin service backed by SqlAlchemyRoleStore.

**************************************************
"""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from cloud_dog_idam.domain.models import Role
from cloud_dog_idam.storage.sqlalchemy.models import (
    PermissionORM as _PermissionORM,
    RoleORM as _RoleORM,
    RolePermissionORM as _RolePermissionORM,
)
from cloud_dog_idam.storage.sqlalchemy.role_store import (
    BaselineRoleProtected,
    SqlAlchemyRoleStore,
)


class RolesAdminError(RuntimeError):
    """Structured roles admin error carrying HTTP status and code."""

    def __init__(self, code: str, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def ensure_role_tables(engine: Engine) -> None:
    """Create the canonical cloud_dog_idam role tables when absent.

    Only the role-related tables (roles, permissions, role_permissions) are
    created here so the PS-71 IW3A Roles page (/api/v1/admin/roles) is backed by
    the shared SqlAlchemyRoleStore. The remaining idam tables are not part of
    this service's schema. Idempotent (checkfirst=True).
    """
    _RoleORM.metadata.create_all(
        bind=engine,
        checkfirst=True,
        tables=[
            _RoleORM.__table__,
            _PermissionORM.__table__,
            _RolePermissionORM.__table__,
        ],
    )


class RolesAdminService:
    """Persistent roles CRUD backed by the cloud_dog_idam role store.

    Sessions are created from the supplied SQLAlchemy Engine (the engine owned
    by the notification-agent DatabaseManager). Each operation runs in its own
    short-lived session, mirroring the file-mcp ``session_manager.session()``
    pattern.
    """

    def __init__(self, *, engine: Engine) -> None:
        self._engine = engine
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    # -- session helper ------------------------------------------------------
    def _session(self) -> Session:
        return self._session_factory()

    @staticmethod
    def _role_payload(role: Role) -> dict[str, Any]:
        return {
            "role_id": role.role_id,
            "name": role.name,
            "description": role.description,
            "permissions": sorted(role.permissions),
        }

    # -- lifecycle -----------------------------------------------------------
    def ensure_roles_seed(self) -> None:
        """Seed the baseline admin/user roles (IW3A.4). Idempotent."""
        session = self._session()
        try:
            SqlAlchemyRoleStore(session).seed_baseline()
            session.commit()
        finally:
            session.close()

    # -- read ----------------------------------------------------------------
    def list_roles(self) -> list[dict[str, Any]]:
        session = self._session()
        try:
            store = SqlAlchemyRoleStore(session)
            store.seed_baseline()
            session.commit()
            return store.list_response()
        finally:
            session.close()

    def get_role(self, role_id: str) -> dict[str, Any]:
        session = self._session()
        try:
            store = SqlAlchemyRoleStore(session)
            store.seed_baseline()
            session.commit()
            for row in store.list_response():
                if row["role_id"] == role_id:
                    return row
            raise RolesAdminError("NOT_FOUND", f"unknown role: {role_id}", status=404)
        finally:
            session.close()

    # -- write ---------------------------------------------------------------
    def create_role(
        self,
        *,
        name: str,
        description: str = "",
        permissions: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise RolesAdminError("VALIDATION_ERROR", "name is required")
        session = self._session()
        try:
            store = SqlAlchemyRoleStore(session)
            store.seed_baseline()
            if store.get_by_name(clean_name) is not None:
                raise RolesAdminError(
                    "CONFLICT", f"role already exists: {clean_name}", status=409
                )
            role = store.save(
                Role(
                    name=clean_name,
                    description=str(description or ""),
                    permissions={
                        str(p).strip() for p in (permissions or []) if str(p).strip()
                    },
                )
            )
            session.commit()
            return self._role_payload(role)
        finally:
            session.close()

    def update_role(self, role_id: str, *, data: dict[str, Any]) -> dict[str, Any]:
        session = self._session()
        try:
            store = SqlAlchemyRoleStore(session)
            store.seed_baseline()
            if store.get(role_id) is None:
                raise RolesAdminError("NOT_FOUND", f"unknown role: {role_id}", status=404)
            raw_perms = data.get("permissions")
            perms = (
                {str(p).strip() for p in raw_perms if str(p).strip()}
                if raw_perms is not None
                else None
            )
            role = store.update(
                role_id, description=data.get("description"), permissions=perms
            )
            session.commit()
            return self._role_payload(role)
        finally:
            session.close()

    def delete_role(self, role_id: str) -> dict[str, Any]:
        session = self._session()
        try:
            store = SqlAlchemyRoleStore(session)
            store.seed_baseline()
            try:
                removed = store.delete(role_id)
            except BaselineRoleProtected as exc:
                raise RolesAdminError(
                    "FORBIDDEN",
                    f"baseline role cannot be deleted: {exc}",
                    status=403,
                )
            if not removed:
                raise RolesAdminError("NOT_FOUND", f"unknown role: {role_id}", status=404)
            session.commit()
            return {"deleted": role_id}
        finally:
            session.close()
