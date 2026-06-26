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
Setup Test Data for T26 Tests
Creates all necessary test users, groups, and configurations to enable all 70 T26 tests
"""

import os
import sys
import httpx
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from src.database.db_manager import get_db_manager
from src.core.users.user_manager import UserManager
from src.core.groups.group_manager import GroupManager
from src.config import get_config

config = get_config()
API_BASE_URL = config.get("api_server.base_url")
API_KEY = config.get("api_server.api_key")
DEFAULT_CHANNEL = config.get("default_channel")
if not API_BASE_URL:
    raise RuntimeError("Missing required configuration: api_server.base_url")
if not API_KEY:
    raise RuntimeError("Missing required configuration: api_server.api_key")
if not DEFAULT_CHANNEL:
    raise RuntimeError("Missing required configuration: default_channel")
TEST_EMAIL_DOMAIN = config.get("test.email_domain")
if not TEST_EMAIL_DOMAIN:
    raise RuntimeError("Missing required configuration: test.email_domain")


def _synthetic_email(local_part: str) -> str:
    return f"{local_part}{TEST_EMAIL_DOMAIN}"

# Test users to create
TEST_USERS = [
    {
        "username": "test_english",
        "email": _synthetic_email("test_english"),
        "display_name": "Test English User",
        "password": "password",
        "language": "en",
        "preferred_channel": DEFAULT_CHANNEL,
        "content_style": "detailed",
        "keywords": ["news", "updates"]
    },
    {
        "username": "test_french",
        "email": _synthetic_email("test_french"),
        "display_name": "Test French User",
        "password": "password",
        "language": "fr",
        "preferred_channel": DEFAULT_CHANNEL,
        "content_style": "summary_link",
        "keywords": ["actualités"]
    },
    {
        "username": "test_spanish",
        "email": _synthetic_email("test_spanish"),
        "display_name": "Test Spanish User",
        "password": "password",
        "language": "es",
        "preferred_channel": DEFAULT_CHANNEL,
        "content_style": "short",
        "keywords": ["noticias"]
    },
    {
        "username": "test_german",
        "email": _synthetic_email("test_german"),
        "display_name": "Test German User",
        "password": "password",
        "language": "de",
        "preferred_channel": DEFAULT_CHANNEL,
        "content_style": "detailed",
        "keywords": ["nachrichten"]
    },
    {
        "username": "test_markdown",
        "email": _synthetic_email("test_markdown"),
        "display_name": "Test Markdown User",
        "password": "password",
        "language": "en",
        "preferred_channel": DEFAULT_CHANNEL,
        "content_style": "detailed",
        "preferred_format": "markdown"
    },
    {
        "username": "test_default",
        "email": _synthetic_email("test_default"),
        "display_name": "Test Default User",
        "password": "password",
        # No preferences - uses defaults
    },
    {
        "username": "test_keywords",
        "email": _synthetic_email("test_keywords"),
        "display_name": "Test Keywords User",
        "password": "password",
        "language": "en",
        "preferred_channel": DEFAULT_CHANNEL,
        "keywords": ["urgent", "important", "alert"]
    },
    {
        "username": "test_disabled",
        "email": _synthetic_email("test_disabled"),
        "display_name": "Test Disabled User",
        "password": "password",
        "language": "en",
        "preferred_channel": DEFAULT_CHANNEL,
        "enabled": False  # Disabled user
    },
    {
        "username": "test_multiple_dest",
        "email": _synthetic_email("test_multiple_dest"),
        "display_name": "Test Multiple Destinations",
        "password": "password",
        "language": "en",
        "preferred_channel": DEFAULT_CHANNEL,
        "additional_channels": ["chat_rest_transparentbordes"]
    },
]

# Test groups to create
TEST_GROUPS = [
    {
        "name": "English Group",
        "description": "Group for English-speaking users",
        "language": "en",
        "content_style": "detailed",
        "members": ["test_english", "test_default", "test_keywords"]
    },
    {
        "name": "French Group",
        "description": "Group for French-speaking users",
        "language": "fr",
        "content_style": "summary_link",
        "members": ["test_french"]
    },
    {
        "name": "Keywords Group",
        "description": "Group with keyword preferences",
        "keywords": ["urgent", "important"],
        "members": ["test_keywords", "test_english"]
    },
    {
        "name": "Default Group",
        "description": "Group with default preferences",
        "members": ["test_default", "test_markdown"]
    },
    {
        "name": "Multi Member Group",
        "description": "Group with multiple members",
        "members": ["test_english", "test_french", "test_spanish", "test_german"]
    }
]


def create_user_via_api(user_data: dict) -> bool:
    """Create a user via API"""
    try:
        client = httpx.Client(
            base_url=API_BASE_URL,
            headers={"X-API-Key": API_KEY},
            timeout=10.0
        )
        
        payload = {
            "username": user_data["username"],
            "email": user_data["email"],
            "display_name": user_data.get("display_name", user_data["username"]),
            "password": user_data.get("password", "password"),
            "role": user_data.get("role", "viewer"),
            "language": user_data.get("language"),
            "preferred_channel": user_data.get("preferred_channel"),
            "content_style": user_data.get("content_style"),
            "preferred_format": user_data.get("preferred_format"),
            "enabled": user_data.get("enabled", True)
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        response = client.post("/api/v1/users", json=payload, timeout=10.0)
        
        if response.status_code in [200, 201]:
            result = response.json()
            user_id = result.get("id") or result.get("user_id")
            
            # Add keywords if provided
            if user_data.get("keywords") and user_id:
                for keyword in user_data["keywords"]:
                    try:
                        client.post(
                            f"/api/v1/users/{user_id}/keywords",
                            json={"keyword": keyword},
                            timeout=5.0
                        )
                    except:
                        pass  # Keywords might not be supported via API
            
            # Add destinations
            if user_data.get("preferred_channel") and user_id:
                try:
                    client.post(
                        f"/api/v1/users/{user_id}/destinations",
                        json={
                            "channel_type": "smtp" if "email" in user_data["preferred_channel"] else "chat_rest",
                            "destination": user_data["email"],
                            "is_primary": True
                        },
                        timeout=5.0
                    )
                except:
                    pass  # Destination might already exist
            
            # Add additional channels
            if user_data.get("additional_channels") and user_id:
                for channel in user_data["additional_channels"]:
                    try:
                        slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
                        if not slack_webhook_url:
                            continue
                        client.post(
                            f"/api/v1/users/{user_id}/destinations",
                            json={
                                "channel_type": "chat_rest",
                                "destination": slack_webhook_url,
                                "is_primary": False
                            },
                            timeout=5.0
                        )
                    except:
                        pass
            
            print(f"✅ Created user: {user_data['username']} ({user_data['email']})")
            return True
        else:
            print(f"⚠️  User {user_data['username']} might already exist: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to create user {user_data['username']}: {e}")
        return False


def create_group_via_api(group_data: dict, user_map: dict) -> bool:
    """Create a group via API"""
    try:
        client = httpx.Client(
            base_url=API_BASE_URL,
            headers={"X-API-Key": API_KEY},
            timeout=10.0
        )
        
        payload = {
            "name": group_data["name"],
            "description": group_data.get("description", ""),
            "language": group_data.get("language"),
            "content_style": group_data.get("content_style"),
            "keywords": group_data.get("keywords", [])
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        response = client.post("/api/v1/groups", json=payload, timeout=10.0)
        
        if response.status_code in [200, 201]:
            result = response.json()
            group_id = result.get("id") or result.get("group_id")
            
            # Add members
            if group_data.get("members") and group_id:
                for username in group_data["members"]:
                    user_id = user_map.get(username)
                    if user_id:
                        try:
                            client.post(
                                f"/api/v1/groups/{group_id}/members",
                                json={"user_id": user_id, "role": "member"},
                                timeout=5.0
                            )
                        except:
                            pass  # Member might already exist
            
            print(f"✅ Created group: {group_data['name']}")
            return True
        else:
            print(f"⚠️  Group {group_data['name']} might already exist: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to create group {group_data['name']}: {e}")
        return False


def main():
    """Main setup function"""
    print("="*70)
    print("T26 Test Data Setup")
    print("="*70)
    print(f"API Base: {API_BASE_URL}")
    print()
    
    # Check API server
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        if response.status_code != 200:
            print("❌ API server is not healthy")
            return 1
    except Exception as e:
        print(f"❌ Cannot connect to API server: {e}")
        print("   Please ensure API server is running on", API_BASE_URL)
        return 1
    
    print("✅ API server is accessible")
    print()
    
    # Create users
    print("Creating test users...")
    user_map = {}  # username -> user_id
    client = httpx.Client(
        base_url=API_BASE_URL,
        headers={"X-API-Key": API_KEY},
        timeout=10.0
    )
    
    for user_data in TEST_USERS:
        create_user_via_api(user_data)
        # Try to get user ID
        try:
            response = client.get(f"/api/v1/users?email={user_data['email']}", timeout=5.0)
            if response.status_code == 200:
                users = response.json().get("items", [])
                if users:
                    user_map[user_data["username"]] = users[0].get("id")
        except:
            pass
    
    print()
    
    # Create groups
    print("Creating test groups...")
    for group_data in TEST_GROUPS:
        create_group_via_api(group_data, user_map)
    
    print()
    print("="*70)
    print("✅ Test data setup complete!")
    print("="*70)
    print()
    print("Created:")
    print(f"  - {len(TEST_USERS)} test users")
    print(f"  - {len(TEST_GROUPS)} test groups")
    print()
    print("You can now run T26 tests:")
    print("  python3 tests/application/AT1.18_T26Comprehensive/test_t26_comprehensive.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

