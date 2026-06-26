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
Description: Group Management API Routes - provides REST endpoints for group CRUD operations

Related Requirements: FR1.13, FR1.14
Related Tasks: T9, T19
Related Architecture: CC1.1, AI1.1
Related Tests: IT1.1

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from pydantic import BaseModel, validator

from src.database.db_manager import get_db_manager
from src.core.groups.group_manager import GroupManager
from src.config import get_config

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    language: Optional[str] = None
    preferred_channel: Optional[str] = None
    content_style: Optional[str] = None
    enabled: bool = True
    keywords: Optional[List[str]] = None

    @validator("language")
    def validate_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return value
        normalized = value.strip().lower()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("language must be an ISO 639-1 two-letter code")
        return normalized

    @validator("content_style")
    def validate_content_style(cls, value: Optional[str]) -> Optional[str]:
        # req: FR-014 — group preference content_style must accept every value the
        # server-rendered WebUI group form offers (html, plain, summary+link) and
        # the prompt renderer supports (W28E-1807B contract alignment).
        if value is None or value == "":
            return value
        normalized = value.strip().lower()
        base = normalized.split(":", 1)[0]
        allowed = {"short", "detailed", "summary+link", "rich", "plain", "html"}
        if base not in allowed:
            raise ValueError("content_style must be one of short, detailed, summary+link, rich, plain, html")
        return normalized

    @validator("keywords")
    def validate_keywords(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item and item.strip()]
        return sorted(set(cleaned))


class GroupUpdate(BaseModel):
    description: Optional[str] = None
    language: Optional[str] = None
    preferred_channel: Optional[str] = None
    content_style: Optional[str] = None
    enabled: Optional[bool] = None
    keywords: Optional[List[str]] = None

    @validator("language")
    def validate_update_language(cls, value: Optional[str]) -> Optional[str]:
        return GroupCreate.validate_language(value)

    @validator("content_style")
    def validate_update_content_style(cls, value: Optional[str]) -> Optional[str]:
        return GroupCreate.validate_content_style(value)

    @validator("keywords")
    def validate_update_keywords(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return GroupCreate.validate_keywords(value)


class MemberAdd(BaseModel):
    user_id: int
    role: str = "member"


class KeywordAdd(BaseModel):
    keyword: str


def _replace_keywords(manager: GroupManager, group_id: int, keywords: Optional[List[str]]) -> None:
    if keywords is None:
        return
    manager.keyword_repo.remove_group_keywords(group_id)
    for keyword in keywords:
        manager.keyword_repo.add(group_id, keyword)

def get_group_manager():
    """Get GroupManager instance"""
    config = get_config()
    db_uri = config.get("db.uri")
    if not db_uri:
        raise RuntimeError("Missing required configuration: db.uri")
    db = get_db_manager(db_uri)
    return GroupManager(db)


_SERVICE_ADMINS = {"notification-api", "bootstrap-admin", "api-runtime"}


def _require_admin(request: Request) -> None:
    """Enforce RBAC admin permission via cloud_dog_idam (PS-70 UM3)."""
    from src.core.idam.runtime import require_authenticated_request, get_idam_runtime
    from src.core.rbac import ADMIN, get_checker_for_user
    principal = require_authenticated_request(request)
    user_id = str(getattr(principal, "user_id", "") or "").strip()
    rt = get_idam_runtime()
    if user_id in _SERVICE_ADMINS:
        # W28A-889-B-R2 / W28A-890: authorize a webui-forwarded request as the
        # FORWARDED web user, not the notification-api service principal, so an
        # authed non-admin web user does not collapse to admin. (See users.py.)
        forwarded_source = str(request.headers.get("X-Request-Source") or "").strip().lower()
        forwarded_user = str(request.headers.get("X-Request-User") or "").strip()
        if forwarded_source == "webui" and forwarded_user:
            forwarded_role = str(request.headers.get("X-Request-Role") or "viewer").strip().lower() or "viewer"
            if rt.rbac_engine.has_permission(forwarded_user, "*"):
                return
            checker = get_checker_for_user({"id": forwarded_user, "role": forwarded_role})
            if not checker.has_permission(ADMIN):
                raise HTTPException(status_code=403, detail="Admin permission required")
            return
        return
    # Check RBAC engine for group-inherited admin permission (PS-70 UM3)
    if rt.rbac_engine.has_permission(user_id, "*"):
        return
    checker = get_checker_for_user({"id": user_id, "role": getattr(principal, "role", "viewer")})
    if not checker.has_permission(ADMIN):
        raise HTTPException(status_code=403, detail="Admin permission required")


@router.get("")
async def list_groups(
    request: Request,
    enabled_only: bool = Query(True, description="Only return enabled groups"),
):
    """List all groups"""
    _require_admin(request)
    manager = get_group_manager()
    loop = asyncio.get_event_loop()
    groups = await loop.run_in_executor(None, manager.list_groups, enabled_only)
    return {"total": len(groups), "items": groups}


@router.post("")
async def create_group(
    request: Request,
    group: GroupCreate,
):
    """Create a new group"""
    _require_admin(request)
    manager = get_group_manager()
    
    try:
        group_id = manager.create_group(
            name=group.name,
            description=group.description,
            language=group.language,
            preferred_channel=group.preferred_channel,
            content_style=group.content_style,
            enabled=group.enabled,
        )
        _replace_keywords(manager, group_id, group.keywords)
        from src.servers.api.api_server import _broadcast_config_event

        await _broadcast_config_event(
            "group",
            "created",
            {
                "id": group_id,
                "name": group.name,
                "description": group.description,
                "language": group.language,
                "preferred_channel": group.preferred_channel,
                "content_style": group.content_style,
            },
        )
        return {"success": True, "group_id": group_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{group_id}")
async def get_group(
    group_id: int,
):
    """Get group by ID with members and keywords"""
    manager = get_group_manager()
    loop = asyncio.get_event_loop()
    group = await loop.run_in_executor(None, manager.get_group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return group


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    group_update: GroupUpdate,
):
    """Update group settings"""
    manager = get_group_manager()
    
    # Verify group exists
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    manager.update_group(
        group_id=group_id,
        description=group_update.description,
        language=group_update.language,
        preferred_channel=group_update.preferred_channel,
        content_style=group_update.content_style,
        enabled=group_update.enabled
    )
    _replace_keywords(manager, group_id, group_update.keywords)
    from src.servers.api.api_server import _broadcast_config_event

    updated = manager.group_repo.get_by_id(group_id)
    await _broadcast_config_event("group", "updated", updated or {"id": group_id})
    return {"success": True, "message": "Group updated"}


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
):
    """Delete a group by ID (and related members/keywords)."""
    manager = get_group_manager()
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    manager.delete_group(group_id)
    from src.servers.api.api_server import _broadcast_config_event

    await _broadcast_config_event("group", "deleted", group)
    return {"success": True, "message": "Group deleted"}


@router.get("/{group_id}/members")
async def list_group_members(
    group_id: int,
):
    """List members of a group."""
    manager = get_group_manager()

    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    loop = asyncio.get_event_loop()
    members = await loop.run_in_executor(None, manager.get_group_members, group_id)
    return members


@router.post("/{group_id}/members")
async def add_member(
    group_id: int,
    member: MemberAdd,
):
    """Add a member to a group"""
    manager = get_group_manager()
    
    # Verify group exists
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Verify user exists
    user = manager.user_repo.get_by_id(member.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    added = manager.add_member(group_id, member.user_id, member.role)

    if not added:
        raise HTTPException(status_code=409, detail="User already in group")
    # Register group membership in RBAC engine for PS-70 UM3 group propagation
    from src.core.idam.runtime import get_idam_runtime
    _rt = get_idam_runtime()
    uid_str = str(member.user_id)
    _rt.rbac_engine.add_user_to_group(uid_str, f"group:{group_id}")
    _rt.rbac_engine._cache.invalidate(f"roles:{uid_str}")  # noqa: SLF001
    _rt.rbac_engine._cache.invalidate(f"perms:{uid_str}")  # noqa: SLF001
    from src.servers.api.api_server import _broadcast_config_event

    await _broadcast_config_event(
        "group",
        "member_added",
        {"group_id": group_id, "user_id": member.user_id, "role": member.role},
    )
    return {"success": True, "message": "Member added"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: int,
    user_id: int,
):
    """Remove a member from a group"""
    manager = get_group_manager()
    
    # Verify group exists
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    manager.remove_member(group_id, user_id)
    # Remove from RBAC engine for PS-70 UM3 group propagation
    from src.core.idam.runtime import get_idam_runtime
    _rt = get_idam_runtime()
    uid_str = str(user_id)
    memberships = _rt.rbac_engine._group_memberships.get(uid_str, set())  # noqa: SLF001
    memberships.discard(f"group:{group_id}")
    _rt.rbac_engine._cache.invalidate(f"roles:{uid_str}")  # noqa: SLF001
    _rt.rbac_engine._cache.invalidate(f"perms:{uid_str}")  # noqa: SLF001
    from src.servers.api.api_server import _broadcast_config_event

    await _broadcast_config_event("group", "member_removed", {"group_id": group_id, "user_id": user_id})
    return {"success": True, "message": "Member removed"}


@router.put("/{group_id}/members/{user_id}/role")
async def update_member_role(
    group_id: int,
    user_id: int,
    role: str = Query(..., description="New role"),
):
    """Update a member's role"""
    manager = get_group_manager()
    
    # Verify group exists
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    manager.update_member_role(group_id, user_id, role)
    return {"success": True, "message": "Role updated"}


@router.post("/{group_id}/keywords")
async def add_keyword(
    group_id: int,
    keyword_data: KeywordAdd,
):
    """Add a keyword to a group"""
    manager = get_group_manager()
    
    # Verify group exists
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    added = manager.add_keyword(group_id, keyword_data.keyword)
    
    if not added:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    
    return {"success": True, "message": "Keyword added"}


@router.delete("/{group_id}/keywords/{keyword}")
async def remove_keyword(
    group_id: int,
    keyword: str,
):
    """Remove a keyword from a group"""
    manager = get_group_manager()
    
    # Verify group exists
    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    manager.remove_keyword(group_id, keyword)
    return {"success": True, "message": "Keyword removed"}
