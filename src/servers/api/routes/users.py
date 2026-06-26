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
Description: User Management API Routes - provides REST endpoints for user CRUD operations

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
from src.core.users.user_manager import UserManager
from src.core.idam.runtime import get_idam_runtime
from src.config import get_config

router = APIRouter(prefix="/users", tags=["users"])
idam_runtime = get_idam_runtime()


class UserPreferencesUpdate(BaseModel):
    language: Optional[str] = None
    preferred_channel: Optional[str] = None
    content_style: Optional[str] = None
    timezone: Optional[str] = None
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
        # req: FR-014 — user preference content_style must accept every value the
        # server-rendered WebUI preference form offers (html, plain) and the
        # prompt renderer supports, not only the legacy {short, detailed,
        # summary+link, rich} set (W28E-1807B: UI offered an option the API rejected).
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


class DestinationCreate(BaseModel):
    channel_type: str
    destination: str
    is_primary: bool = False
    metadata: Optional[dict] = None


class KeywordAdd(BaseModel):
    keyword: str


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    display_name: Optional[str] = None
    role: str = "viewer"
    user_type: str = "real"
    language: Optional[str] = None
    preferred_channel: Optional[str] = None
    content_style: Optional[str] = None
    timezone: Optional[str] = None

    @validator("language")
    def validate_create_language(cls, value: Optional[str]) -> Optional[str]:
        return UserPreferencesUpdate.validate_language(value)

    @validator("content_style")
    def validate_create_content_style(cls, value: Optional[str]) -> Optional[str]:
        return UserPreferencesUpdate.validate_content_style(value)


class UserEnabledUpdate(BaseModel):
    enabled: bool


def get_user_manager():
    """Get UserManager instance"""
    config = get_config()
    db_uri = config.get("db.uri")
    if not db_uri:
        raise RuntimeError("Missing required configuration: db.uri")
    db = get_db_manager(db_uri)
    return UserManager(db)


_SERVICE_ADMINS = {"notification-api", "bootstrap-admin", "api-runtime"}


def _require_admin(request: Request) -> None:
    """Enforce RBAC admin permission via cloud_dog_idam (PS-70 UM3)."""
    from src.core.idam.runtime import require_authenticated_request, get_idam_runtime
    from src.core.rbac import ADMIN, get_checker_for_user
    principal = require_authenticated_request(request)
    user_id = str(getattr(principal, "user_id", "") or "").strip()
    rt = get_idam_runtime()
    if user_id in _SERVICE_ADMINS:
        # W28A-889-B-R2 / W28A-890: the web proxy authenticates with the
        # notification-api service key (a _SERVICE_ADMINS member) but forwards the
        # real web user (X-Request-Source=webui + X-Request-User/Role). Authorize as
        # the FORWARDED user so an authed non-admin web user does NOT collapse to
        # admin. A non-service api-key cannot reach this branch, so it cannot escalate.
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
        # Genuine service principal (MCP/A2A/direct service call), no web forwarding.
        return
    # Check RBAC engine for group-inherited admin permission (PS-70 UM3)
    if rt.rbac_engine.has_permission(user_id, "*"):
        return
    checker = get_checker_for_user({"id": user_id, "role": getattr(principal, "role", "viewer")})
    if not checker.has_permission(ADMIN):
        raise HTTPException(status_code=403, detail="Admin permission required")


def _authenticated_user_lookup(request: Request) -> tuple[str, Optional[int]]:
    from src.core.idam.runtime import require_authenticated_request

    principal = require_authenticated_request(request)
    raw_user_id = str(getattr(principal, "user_id", "") or "").strip()
    if raw_user_id in _SERVICE_ADMINS:
        forwarded_source = str(request.headers.get("X-Request-Source") or "").strip().lower()
        forwarded_user = str(request.headers.get("X-Request-User") or "").strip()
        if forwarded_source == "webui" and forwarded_user:
            raw_user_id = forwarded_user
    numeric_id = int(raw_user_id) if raw_user_id.isdigit() else None
    return raw_user_id, numeric_id


async def _resolve_current_user(request: Request) -> dict:
    raw_user_id, numeric_id = _authenticated_user_lookup(request)
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    if numeric_id is not None:
        user = await loop.run_in_executor(None, manager.user_repo.get_by_id, numeric_id)
        if user:
            return user
    user = await loop.run_in_executor(None, manager.user_repo.get_by_username, raw_user_id)
    if user:
        return user
    raise HTTPException(status_code=404, detail="Current user profile not found")


def _replace_keywords(manager: UserManager, user_id: int, keywords: Optional[List[str]]) -> None:
    if keywords is None:
        return
    for existing in manager.keyword_repo.get_by_user_id(user_id):
        manager.keyword_repo.remove(user_id, existing["keyword"])
    for keyword in keywords:
        manager.keyword_repo.add(user_id, keyword)


@router.get("")
async def list_users(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    limit: int = Query(1000, ge=1, le=1000),
):
    """List users or search users"""
    _require_admin(request)
    manager = get_user_manager()
    
    loop = asyncio.get_event_loop()
    if q:
        users = await loop.run_in_executor(None, manager.search_users, q, limit)
    else:
        # List all users (using search with empty query to get all)
        # We'll use the repository directly to get all users
        from src.database.repositories import UserRepository
        from src.database.db_manager import get_db_manager
        from src.config import get_config
        
        config = get_config()
        db_uri = config.get("db.uri")
        if not db_uri:
            raise RuntimeError("Missing required configuration: db.uri")
        db = get_db_manager(db_uri)
        user_repo = UserRepository(db)
        users = await loop.run_in_executor(None, user_repo.list_all, limit)
    
    return {"total": len(users), "items": users}


@router.get("/me/preferences")
async def get_my_preferences(request: Request):
    """Return the authenticated user's self-service preference profile."""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    user = await _resolve_current_user(request)
    full_user = await loop.run_in_executor(None, manager.get_user_with_destinations, int(user["id"]))
    return full_user


@router.put("/me/preferences")
async def update_my_preferences(request: Request, preferences: UserPreferencesUpdate):
    """Update the authenticated user's own preference profile."""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    user = await _resolve_current_user(request)
    user_id = int(user["id"])
    await loop.run_in_executor(None, lambda: manager.update_preferences(
        user_id=user_id,
        language=preferences.language,
        preferred_channel=preferences.preferred_channel,
        content_style=preferences.content_style,
        timezone=preferences.timezone,
    ))
    await loop.run_in_executor(None, _replace_keywords, manager, user_id, preferences.keywords)
    return await loop.run_in_executor(None, manager.get_user_with_destinations, user_id)


@router.delete("/me/preferences")
async def delete_my_preferences(request: Request):
    """Clear the authenticated user's preference profile and keywords."""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    user = await _resolve_current_user(request)
    user_id = int(user["id"])
    await loop.run_in_executor(None, manager.user_repo.clear_preferences, user_id)
    await loop.run_in_executor(None, _replace_keywords, manager, user_id, [])
    return {"success": True, "user_id": user_id}


@router.post("")
async def create_user(
    request: Request,
    user_data: UserCreate,
):
    """Create a new user"""
    _require_admin(request)
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    # Check if user already exists
    existing = await loop.run_in_executor(None, manager.user_repo.get_by_username, user_data.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    existing = await loop.run_in_executor(None, manager.user_repo.get_by_email, user_data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")
    
    password_hash = idam_runtime.hash_password(user_data.password)
    
    # Create user
    user_id = await loop.run_in_executor(None, lambda: manager.user_repo.create(
        username=user_data.username,
        email=user_data.email,
        password_hash=password_hash,
        role=user_data.role,
        display_name=user_data.display_name,
        user_type=user_data.user_type,
        language=user_data.language,
        preferred_channel=user_data.preferred_channel,
        content_style=user_data.content_style,
        timezone=user_data.timezone,
    ))
    
    return {
        "success": True,
        "user_id": user_id,
        "message": "User created successfully"
    }


@router.get("/{user_id}")
async def get_user(
    user_id: int,
):
    """Get user by ID with destinations and keywords"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    user = await loop.run_in_executor(None, manager.get_user_with_destinations, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.delete("/{user_id}")
async def delete_user(
    request: Request,
    user_id: int,
):
    """Delete user by ID (and related destinations/keywords/group memberships)."""
    _require_admin(request)
    manager = get_user_manager()
    loop = asyncio.get_event_loop()

    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await loop.run_in_executor(None, manager.user_repo.delete, user_id)
    return {"success": True, "message": "User deleted"}


@router.patch("/{user_id}/enabled")
async def set_user_enabled(
    request: Request,
    user_id: int,
    payload: UserEnabledUpdate,
):
    """Enable or disable a user."""
    _require_admin(request)
    manager = get_user_manager()
    loop = asyncio.get_event_loop()

    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await loop.run_in_executor(None, manager.user_repo.set_enabled, user_id, bool(payload.enabled))
    return {"success": True, "user_id": user_id, "enabled": bool(payload.enabled)}


@router.get("/search/{query}")
async def search_users(
    query: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Search users by username, email, or display_name"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    users = await loop.run_in_executor(None, manager.search_users, query, limit)
    return {"total": len(users), "items": users}


@router.put("/{user_id}/preferences")
async def update_user_preferences(
    request: Request,
    user_id: int,
    preferences: UserPreferencesUpdate,
):
    """Update user preferences"""
    _require_admin(request)
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    # Verify user exists
    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await loop.run_in_executor(None, lambda: manager.update_preferences(
        user_id=user_id,
        language=preferences.language,
        preferred_channel=preferences.preferred_channel,
        content_style=preferences.content_style,
        timezone=preferences.timezone
    ))
    await loop.run_in_executor(None, _replace_keywords, manager, user_id, preferences.keywords)
    
    return {"success": True, "message": "Preferences updated"}


@router.delete("/{user_id}/preferences")
async def delete_user_preferences(
    request: Request,
    user_id: int,
):
    """Clear user preferences and personalization keywords."""
    _require_admin(request)
    manager = get_user_manager()
    loop = asyncio.get_event_loop()

    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await loop.run_in_executor(None, manager.user_repo.clear_preferences, user_id)
    await loop.run_in_executor(None, _replace_keywords, manager, user_id, [])
    return {"success": True, "message": "Preferences deleted"}


@router.post("/{user_id}/destinations")
async def add_destination(
    user_id: int,
    destination: DestinationCreate,
):
    """Add a destination for a user"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    # Verify user exists
    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    dest_id = await loop.run_in_executor(None, lambda: manager.add_destination(
        user_id=user_id,
        channel_type=destination.channel_type,
        destination=destination.destination,
        is_primary=destination.is_primary,
        metadata=destination.metadata
    ))
    
    return {"success": True, "destination_id": dest_id}


@router.delete("/{user_id}/destinations/{destination_id}")
async def remove_destination(
    user_id: int,
    destination_id: int,
):
    """Remove a destination from a user"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    try:
        await loop.run_in_executor(None, manager.remove_destination, destination_id, user_id)
        return {"success": True, "message": "Destination removed"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{user_id}/destinations/{destination_id}/primary")
async def set_primary_destination(
    user_id: int,
    destination_id: int,
):
    """Set a destination as primary"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    try:
        await loop.run_in_executor(None, manager.set_primary_destination, destination_id, user_id)
        return {"success": True, "message": "Primary destination set"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{user_id}/keywords")
async def add_keyword(
    user_id: int,
    keyword_data: KeywordAdd,
):
    """Add a keyword to a user"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    # Verify user exists
    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    added = await loop.run_in_executor(None, manager.add_keyword, user_id, keyword_data.keyword)
    
    if not added:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    
    return {"success": True, "message": "Keyword added"}


@router.delete("/{user_id}/keywords/{keyword}")
async def remove_keyword(
    user_id: int,
    keyword: str,
):
    """Remove a keyword from a user"""
    manager = get_user_manager()
    loop = asyncio.get_event_loop()
    
    # Verify user exists
    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await loop.run_in_executor(None, manager.remove_keyword, user_id, keyword)
    return {"success": True, "message": "Keyword removed"}
