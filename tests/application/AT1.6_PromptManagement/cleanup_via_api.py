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
AT1.6 - API Cleanup Helper
Tests that ALL cleanup operations are available via API
"""
import httpx
import sys
from typing import Any
from src.config import get_config

config = get_config()
API_URL = config.get("api_server.base_url")
API_KEY = config.get("api_server.api_key")
if not API_URL:
    raise RuntimeError("Missing required configuration: api_server.base_url")
if not API_KEY:
    raise RuntimeError("Missing required configuration: api_server.api_key")

def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

async def cleanup_all():
    """Delete all test resources via API only"""
    headers = {"X-API-Key": API_KEY}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🧹 Cleaning via API (100% API, NO database access)...")
        
        # 1. Get all users
        users = _items((await client.get(f"{API_URL}/users", headers=headers)).json())
        for user in users:
            if user['id'] >= 6:  # Don't delete admin/core users
                resp = await client.delete(f"{API_URL}/users/{user['id']}", headers=headers)
                print(f"✅ DELETE /users/{user['id']}: {resp.status_code}")
        
        # 2. Get all prompts
        prompts = (await client.get(f"{API_URL}/prompts", headers=headers)).json()
        for prompt in prompts:
            if prompt['id'] >= 7:  # Don't delete core prompts
                resp = await client.delete(f"{API_URL}/prompts/{prompt['id']}", headers=headers)
                print(f"✅ DELETE /prompts/{prompt['id']}: {resp.status_code}")
        
        # 3. Get all groups
        groups = (await client.get(f"{API_URL}/groups", headers=headers)).json()
        for group in groups:
            resp = await client.delete(f"{API_URL}/groups/{group['id']}", headers=headers)
            print(f"✅ DELETE /groups/{group['id']}: {resp.status_code}")
        
        # 4. Get all messages
        messages = (await client.get(f"{API_URL}/messages", headers=headers)).json()
        if isinstance(messages, dict) and 'items' in messages:
            messages = messages['items']
        for msg in messages:
            if msg['id'] >= 23:  # Don't delete old messages
                resp = await client.delete(f"{API_URL}/messages/{msg['id']}", headers=headers)
                print(f"✅ DELETE /messages/{msg['id']}: {resp.status_code}")
        
        print("\n✅ Cleanup complete - 100% via API")

if __name__ == "__main__":
    import asyncio
    asyncio.run(cleanup_all())
