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
Description: RBAC module — re-exports permission constants and helpers from cloud_dog_idam.

Related Requirements: CS1.1, FR1.14
Related Tasks: T22, T29
Related Architecture: SE1.1, SE1.5
Related Tests: IT1.11

Recent Changes (max 10):
- 2026-04-07: W28A-699 — Replaced bespoke exports with cloud_dog_idam-backed constants.

**************************************************
"""

from cloud_dog_idam.rbac import PermissionChecker

from .permissions import (
    ADMIN,
    CONFIG_READ,
    CONFIG_WRITE,
    DELETE_ITEM,
    LIST,
    READ_ITEM,
    SEND,
    get_checker_for_user,
    list_role_permissions,
)

__all__ = [
    "SEND",
    "LIST",
    "READ_ITEM",
    "DELETE_ITEM",
    "CONFIG_WRITE",
    "CONFIG_READ",
    "ADMIN",
    "PermissionChecker",
    "get_checker_for_user",
    "list_role_permissions",
]
