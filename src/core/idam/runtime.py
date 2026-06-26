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
Description: IDAM runtime integration helpers backed by cloud_dog_idam

Related Requirements: CS1.1, FR1.14
Related Tasks: T22, T29
Related Architecture: SE1.1
Related Tests: IT1.11

Recent Changes (max 10):
- 2026-03-03: Added cloud_dog_idam runtime bridge for API auth, RBAC and password hashing.

**************************************************
"""

from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from typing import Any, Dict, Iterable
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
from fastapi import HTTPException, Request, status

from cloud_dog_idam import APIKeyManager, RBACEngine
from cloud_dog_idam.api.fastapi.middleware import AuthContextMiddleware
from cloud_dog_idam.api_keys.hashing import hash_api_key
from cloud_dog_idam.audit.emitter import AuditEmitter
from cloud_dog_idam.domain.models import ApiKey
from cloud_dog_idam.providers.local_password import LocalPasswordProvider

from src.config import get_config


DEFAULT_ROLE_PERMISSIONS: Dict[str, set[str]] = {
    "admin": {"*"},
    "owner": {
        "notification:send:execute",
        "notification:item:read",
        "notification:item:delete",
        "notification:list:read",
        "notification:config:read",
    },
    "user": {
        "notification:send:execute",
        "notification:item:read",
        "notification:config:read",
        "notification:list:read",
    },
    "viewer": {
        "notification:item:read",
        "notification:config:read",
        "notification:list:read",
    },
    # W28A-744: flat-login roles (730-R5) mapped to channel domain perms so the
    # W28A-741 cascade list-filter does not hide channels from flat principals.
    # The W28A-741 merge with the PS-82 baseline keeps admin=* intact.
    "read-write": {
        "channel.read",
        "channel.write",
        "notification:send:execute",
        "notification:item:read",
        "notification:item:delete",
        "notification:config:read",
        "notification:list:read",
    },
    "read-only": {
        "channel.read",
        "notification:item:read",
        "notification:config:read",
        "notification:list:read",
    },
    # restricted: PS-82 quarantined principal — NO flat channel grant; access to a
    # channel comes ONLY via an RBACBinding (the provable cascade GROUPUSER).
    "restricted": set(),
}


def _normalise_role_permissions(raw: Any) -> Dict[str, set[str]]:
    if not isinstance(raw, dict):
        return {k: set(v) for k, v in DEFAULT_ROLE_PERMISSIONS.items()}

    normalised: Dict[str, set[str]] = {}
    for role_name, permissions in raw.items():
        role = str(role_name).strip().lower()
        if not role:
            continue
        if isinstance(permissions, (list, tuple, set)):
            normalised[role] = {str(item).strip() for item in permissions if str(item).strip()}
        elif isinstance(permissions, str) and permissions.strip():
            normalised[role] = {permissions.strip()}
    if not normalised:
        return {k: set(v) for k, v in DEFAULT_ROLE_PERMISSIONS.items()}
    return normalised


@dataclass
class IDAMRuntime:
    api_key_manager: APIKeyManager
    rbac_engine: RBACEngine
    audit_emitter: AuditEmitter
    password_provider: LocalPasswordProvider

    def seed_api_key(self, api_key: str, owner_user_id: str = "api-runtime") -> None:
        raw_key = str(api_key or "").strip()
        if not raw_key:
            return
        if self.api_key_manager.validate(raw_key) is not None:
            return
        item = ApiKey(
            api_key_id=str(uuid4()),
            owner_user_id=owner_user_id,
            key_prefix=raw_key[:3] if len(raw_key) >= 3 else "cd_",
            key_hash=hash_api_key(raw_key),
            status="active",
        )
        # APIKeyManager does not currently expose a public insert method.
        self.api_key_manager._keys[item.api_key_id] = item  # noqa: SLF001

    def install_auth_middleware(
        self,
        app: Any,
        *,
        auth_scheme: str = "api_key",
        skip_paths: Iterable[str] | None = None,
    ) -> None:
        skip_set = set(skip_paths or {"/health", "/ready", "/live", "/docs", "/openapi.json"})
        if "api_key_manager" not in signature(AuthContextMiddleware.__init__).parameters:
            raise RuntimeError("cloud_dog_idam AuthContextMiddleware is incompatible with this runtime")
        app.add_middleware(
            AuthContextMiddleware,
            api_key_manager=self.api_key_manager,
            rbac_engine=self.rbac_engine,
            audit_emitter=self.audit_emitter,
            auth_scheme=auth_scheme,
            skip_paths=skip_set,
        )

    def hash_password(self, raw_password: str) -> str:
        return self.password_provider.hash_password(raw_password)

    def verify_password(self, raw_password: str, stored_hash: str) -> bool:
        if not stored_hash:
            return False
        verifier = getattr(self.password_provider, "verify_password", None)
        if callable(verifier):
            return bool(verifier(raw_password, stored_hash))
        try:
            PasswordHasher().verify(stored_hash, raw_password)
            return True
        except Argon2Error:
            return False


_RUNTIME: IDAMRuntime | None = None


def get_idam_runtime(*, force_reload: bool = False) -> IDAMRuntime:
    global _RUNTIME
    if _RUNTIME is not None and not force_reload:
        return _RUNTIME

    config = get_config()
    role_permissions = _normalise_role_permissions(config.get("auth.rbac.role_permissions"))
    audit_path = config.get("log.audit_log")
    audit_emitter = AuditEmitter(log_path=audit_path if audit_path else None)
    password_provider = LocalPasswordProvider(lambda _: None)

    _RUNTIME = IDAMRuntime(
        api_key_manager=APIKeyManager(),
        rbac_engine=RBACEngine(role_overlay=role_permissions),
        audit_emitter=audit_emitter,
        password_provider=password_provider,
    )
    return _RUNTIME


def require_authenticated_request(request: Request) -> Any:
    principal = getattr(request.state, "user", None)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return principal
