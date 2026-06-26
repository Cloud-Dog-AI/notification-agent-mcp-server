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
Description: User Initializer for Notification Agent MCP Server - Creates users from configuration on startup if they don't exist, reads from config.users.* structure

Related Requirements: FR1.13
Related Tasks: T4, T19
Related Architecture: CC4.1
Related Tests: UT1.8

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from typing import Dict, Any
from src.core.idam.runtime import get_idam_runtime
from src.core.users.user_manager import UserManager
from src.database.repositories import ChannelRepository
from src.database.db_manager import DatabaseManager
from src.utils.logger import get_logger

logger = get_logger(__name__)
idam_runtime = get_idam_runtime()


def initialize_users_from_config(db: DatabaseManager, config: Dict[str, Any]):
    """
    Initialize users from configuration on startup.
    
    Reads users from config.users.* structure and creates them if they don't exist.
    Expected config structure:
    {
            "users": {
                "example_user": {
                "email": "<USER_EMAIL>",
                "username": "<USERNAME>",
                "display_name": "<DISPLAY_NAME>",
                "password": "<PASSWORD>",
                "language": "en",
                "preferred_channel": "<DEFAULT_CHANNEL_NAME>",
                "content_style": "detailed"
            },
            ...
        }
    }
    
    Args:
        db: DatabaseManager instance
        config: Configuration dictionary
    """
    users_config = config.get("users", {})
    if not users_config:
        logger.debug("No users configured in config.users")
        return
    
    user_manager = UserManager(db)
    channel_repo = ChannelRepository(db)
    created_count = 0
    updated_count = 0
    
    for user_key, user_data in users_config.items():
        if not isinstance(user_data, dict):
            logger.warning(f"Skipping invalid user config for '{user_key}': not a dict")
            continue
        
        email = user_data.get("email")
        username = user_data.get("username") or user_key.lower()
        display_name = user_data.get("display_name") or username
        password = user_data.get("password")
        language = user_data.get("language")
        preferred_channel = user_data.get("preferred_channel")
        content_style = user_data.get("content_style")
        role = user_data.get("role")
        user_type = user_data.get("user_type")
        
        if not email or not password or not role or not user_type:
            missing_fields = [field for field, value in {
                "email": email,
                "password": password,
                "role": role,
                "user_type": user_type,
            }.items() if not value]
            logger.warning(f"Skipping user '{user_key}': missing {', '.join(missing_fields)}")
            continue
        
        # Check if user exists by email
        existing_user = user_manager.user_repo.get_by_email(email)
        if existing_user:
            user_id = existing_user["id"]
            logger.debug(f"User '{username}' ({email}) already exists (ID: {user_id})")
            
            # Update preferences if provided and different
            needs_update = False
            if language and existing_user.get("language") != language:
                needs_update = True
            if preferred_channel and existing_user.get("preferred_channel") != preferred_channel:
                needs_update = True
            if content_style and existing_user.get("content_style") != content_style:
                needs_update = True
            
            if needs_update:
                user_manager.update_preferences(
                    user_id=user_id,
                    language=language,
                    preferred_channel=preferred_channel,
                    content_style=content_style
                )
                logger.info(f"Updated preferences for user '{username}' ({email})")
                updated_count += 1
            
            # Ensure email destination exists
            if preferred_channel:
                # Map channel name to channel_type
                channel = channel_repo.get_by_name(preferred_channel)
                if not channel:
                    logger.warning(f"Unknown channel '{preferred_channel}' for user '{username}', skipping destination")
                    continue
                channel_type = channel.get("type")
                
                # Check if destination exists
                destinations = user_manager.destination_repo.get_by_user_id(user_id)
                email_dest = next((d for d in destinations if d.get("channel_type") == channel_type and d.get("destination") == email), None)
                
                if not email_dest:
                    try:
                        user_manager.add_destination(
                            user_id=user_id,
                            channel_type=channel_type,
                            destination=email,
                            is_primary=True
                        )
                        logger.info(f"Added {channel_type} destination for user '{username}' ({email})")
                    except Exception as e:
                        logger.warning(f"Failed to add destination for '{username}': {e}")
            
            continue
        
        # Check if username exists
        existing_by_username = user_manager.user_repo.get_by_username(username)
        if existing_by_username:
            logger.warning(f"Username '{username}' already exists with different email, skipping")
            continue
        
        # Create new user
        try:
            password_hash = idam_runtime.hash_password(password)
            
            # Create user
            user_id = user_manager.user_repo.create(
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
                display_name=display_name,
                user_type=user_type,
                language=language,
                preferred_channel=preferred_channel,
                content_style=content_style,
                timezone=None
            )
            
            logger.info(f"Created user '{username}' ({email}) from config (ID: {user_id})")
            created_count += 1
            
            # Add email destination if preferred_channel is set
            if preferred_channel:
                channel = channel_repo.get_by_name(preferred_channel)
                if not channel:
                    logger.warning(f"Unknown channel '{preferred_channel}' for user '{username}', skipping destination")
                    continue
                channel_type = channel.get("type")
                
                try:
                    user_manager.add_destination(
                        user_id=user_id,
                        channel_type=channel_type,
                        destination=email,
                        is_primary=True
                    )
                    logger.info(f"Added {channel_type} destination for user '{username}' ({email})")
                except Exception as e:
                    logger.warning(f"Failed to add destination for '{username}': {e}")
        
        except Exception as e:
            logger.error(f"Failed to create user '{username}' ({email}): {e}", exc_info=True)
    
    if created_count > 0 or updated_count > 0:
        logger.info(f"User initialization complete: {created_count} created, {updated_count} updated")
    else:
        logger.debug("User initialization complete: no changes needed")
