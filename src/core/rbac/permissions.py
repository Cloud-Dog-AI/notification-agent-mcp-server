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
Description: Permission constants and RBAC helpers backed by cloud_dog_idam.rbac.RBACEngine.
    All permission checks delegate to cloud_dog_idam — no bespoke RBAC logic.

Related Requirements: CS1.1, FR1.14, PS-70 UM3
Related Tasks: T22, T29
Related Architecture: SE1.1, SE1.5
Related Tests: IT1.11

Recent Changes (max 10):
- 2026-04-07: W28A-699 — Replaced bespoke PermissionChecker/Role/Permission enums with
  cloud_dog_idam.rbac.PermissionChecker and string constants.
- 2026-03-03: Migrated permission checks to cloud_dog_idam RBAC engine with config-driven role mappings.

**************************************************
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from cloud_dog_idam.rbac import PermissionChecker

from src.core.idam.runtime import get_idam_runtime


# --- Permission string constants (PS-70 UM3.3 resource:action format) ---

SEND = "notification:send:execute"
LIST = "notification:list:read"
READ_ITEM = "notification:item:read"
DELETE_ITEM = "notification:item:delete"
CONFIG_WRITE = "notification:config:write"
CONFIG_READ = "notification:config:read"
ADMIN = "notification:admin:*"


def list_role_permissions(role_name: str) -> List[str]:
    """Return concrete permission strings for a role via cloud_dog_idam RBACEngine."""
    runtime = get_idam_runtime()
    principal = f"role:{role_name}"
    runtime.rbac_engine.assign_role_to_user(principal, role_name)
    return sorted(runtime.rbac_engine.get_effective_permissions(principal))


def get_checker_for_user(
    user_data: Dict[str, Any], owned_groups: Optional[List[int]] = None
) -> PermissionChecker:
    """Create a cloud_dog_idam PermissionChecker for the given user context."""
    runtime = get_idam_runtime()
    role = str(user_data.get("role") or "viewer").strip().lower()
    user_id = str(user_data.get("id", 0))
    principal = f"user:{user_id}"
    runtime.rbac_engine.assign_role_to_user(principal, role)
    perms = runtime.rbac_engine.get_effective_permissions(principal)
    owned = {str(g) for g in (owned_groups or [])}
    return PermissionChecker(permissions=perms, user_id=user_id, owned_groups=owned)
