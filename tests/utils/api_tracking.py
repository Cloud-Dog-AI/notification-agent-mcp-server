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
API client wrappers to track created resources and clean up after tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import httpx


@dataclass
class ApiCleanupRegistry:
    base_url: str
    api_key: str
    timeout: float
    messages: Set[str] = field(default_factory=set)
    users: Set[int] = field(default_factory=set)
    groups: Set[int] = field(default_factory=set)
    group_members: Set[Tuple[int, int]] = field(default_factory=set)
    prompts: Set[int] = field(default_factory=set)
    channels: Set[int] = field(default_factory=set)

    def register_message(self, message_id: Optional[str]) -> None:
        if message_id:
            self.messages.add(str(message_id))

    def register_user(self, user_id: Optional[int]) -> None:
        if user_id is not None:
            self.users.add(int(user_id))

    def register_group(self, group_id: Optional[int]) -> None:
        if group_id is not None:
            self.groups.add(int(group_id))

    def register_group_member(self, group_id: Optional[int], member_id: Optional[int]) -> None:
        if group_id is not None and member_id is not None and int(member_id) > 0:
            self.group_members.add((int(group_id), int(member_id)))

    def register_prompt(self, prompt_id: Optional[int]) -> None:
        if prompt_id is not None:
            self.prompts.add(int(prompt_id))

    def register_channel(self, channel_id: Optional[int]) -> None:
        if channel_id is not None:
            self.channels.add(int(channel_id))

    def track_response(self, response: httpx.Response) -> None:
        if response.request.method.upper() != "POST":
            return
        if response.status_code not in (200, 201):
            return
        try:
            payload = response.json()
        except ValueError:
            return

        path = response.request.url.path
        if path.endswith("/messages"):
            self.register_message(payload.get("message_id") or payload.get("id"))
            return
        if path.endswith("/users"):
            self.register_user(payload.get("id"))
            return
        if path.endswith("/groups"):
            self.register_group(payload.get("id"))
            return
        if "/groups/" in path and path.endswith("/members"):
            try:
                group_id = int(path.split("/groups/")[1].split("/")[0])
            except (ValueError, IndexError):
                group_id = None
            self.register_group_member(group_id, payload.get("id"))
            return
        if path.endswith("/prompts"):
            self.register_prompt(payload.get("id"))
            return
        if path.endswith("/channels"):
            self.register_channel(payload.get("id"))

    def cleanup(self) -> None:
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=headers) as client:
                for message_id in list(self.messages):
                    try:
                        client.delete(f"/messages/{message_id}")
                    except Exception:
                        continue
                for prompt_id in list(self.prompts):
                    try:
                        client.delete(f"/prompts/{prompt_id}")
                    except Exception:
                        continue
                for group_id, member_id in list(self.group_members):
                    try:
                        client.delete(f"/groups/{group_id}/members/{member_id}")
                    except Exception:
                        continue
                for group_id in list(self.groups):
                    try:
                        client.delete(f"/groups/{group_id}")
                    except Exception:
                        continue
                for user_id in list(self.users):
                    try:
                        client.delete(f"/users/{user_id}")
                    except Exception:
                        continue
                for channel_id in list(self.channels):
                    # No delete endpoint; disable channel as best-effort cleanup.
                    try:
                        client.post(f"/channels/{channel_id}/disable")
                    except Exception:
                        continue
        except Exception:
            return


class TrackedClient:
    def __init__(self, client: httpx.Client, registry: ApiCleanupRegistry):
        self._client = client
        self._registry = registry

    def __enter__(self) -> "TrackedClient":
        self._client.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return self._client.__exit__(exc_type, exc, tb)

    def __getattr__(self, name):
        return getattr(self._client, name)

    def post(self, *args, **kwargs) -> httpx.Response:
        response = self._client.post(*args, **kwargs)
        self._registry.track_response(response)
        return response


class TrackedAsyncClient:
    def __init__(self, client: httpx.AsyncClient, registry: ApiCleanupRegistry):
        self._client = client
        self._registry = registry

    async def __aenter__(self) -> "TrackedAsyncClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return await self._client.__aexit__(exc_type, exc, tb)

    def __getattr__(self, name):
        return getattr(self._client, name)

    async def post(self, *args, **kwargs) -> httpx.Response:
        response = await self._client.post(*args, **kwargs)
        self._registry.track_response(response)
        return response


def build_tracked_client(
    base_url: str,
    api_key: str,
    timeout: float,
    registry: ApiCleanupRegistry,
    headers: Optional[Dict[str, str]] = None,
) -> TrackedClient:
    merged_headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    client = httpx.Client(base_url=base_url, timeout=timeout, headers=merged_headers)
    return TrackedClient(client, registry)


def build_tracked_async_client(
    base_url: str,
    api_key: str,
    timeout: float,
    registry: ApiCleanupRegistry,
    headers: Optional[Dict[str, str]] = None,
) -> TrackedAsyncClient:
    merged_headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=merged_headers)
    return TrackedAsyncClient(client, registry)
