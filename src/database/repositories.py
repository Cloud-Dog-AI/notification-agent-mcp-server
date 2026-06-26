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
Description: Repository layer for database operations - provides data access layer for messages, deliveries, channels, users, templates, and audit events

Related Requirements: FR1.3, FR1.4, FR1.5, NF1.2
Related Tasks: T4
Related Architecture: CC6.1, DM1.1
Related Tests: UT1.2, IT1.1

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from src.utils.logger import get_logger
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from .db_manager import DatabaseManager

logger = get_logger(__name__)


class BaseRepository:
    """Base repository with common operations"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize repository
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
    
    def _row_to_dict(self, row) -> Optional[Dict]:
        """Convert database row to dictionary"""
        return dict(row) if row else None


class MessageRepository(BaseRepository):
    """Repository for messages table"""
    
    def create(
        self,
        created_by: str,
        audience_type: str,
        content_json: str,
        template_ref: Optional[str] = None,
        variables_json: Optional[str] = None,
        llm_profile: Optional[str] = None,
        ttl_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
        status: str = "queued",
        subject: Optional[str] = None,
    ) -> int:
        """Create a new message with GUID and optional subject."""
        import uuid
        import json as _json
        guid = str(uuid.uuid4())

        # W28D-440A: extract subject from variables_json if not explicitly provided
        if subject is None and variables_json:
            try:
                vj = _json.loads(variables_json) if isinstance(variables_json, str) else variables_json
                subject = vj.get("subject") if isinstance(vj, dict) else None
            except Exception:
                pass

        # W28D-440A: try with subject column first, fall back without it
        try:
            cursor = self.db.execute(
                """
                INSERT INTO messages (
                    created_by, audience_type, content_json, template_ref,
                    variables_json, llm_profile, ttl_at, idempotency_key, status, guid, subject
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (created_by, audience_type, content_json, template_ref,
                 variables_json, llm_profile, ttl_at, idempotency_key, status, guid, subject)
            )
        except Exception:
            # Subject column may not exist yet (pre-migration 006)
            cursor = self.db.execute(
                """
                INSERT INTO messages (
                    created_by, audience_type, content_json, template_ref,
                    variables_json, llm_profile, ttl_at, idempotency_key, status, guid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (created_by, audience_type, content_json, template_ref,
                 variables_json, llm_profile, ttl_at, idempotency_key, status, guid)
            )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_id(self, message_id: int) -> Optional[Dict]:
        """Get message by ID"""
        return self.db.fetchone(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,)
        )
    
    def get_by_guid(self, guid: str) -> Optional[Dict]:
        """Get message by GUID (exact match)"""
        return self.db.fetchone(
            "SELECT * FROM messages WHERE guid = ?",
            (guid,)
        )
    
    def get_by_idempotency_key(self, key: str) -> Optional[Dict]:
        """Get message by idempotency key"""
        return self.db.fetchone(
            "SELECT * FROM messages WHERE idempotency_key = ?",
            (key,)
        )
    
    def update_status(self, message_id: int, status: str):
        """Update message status"""
        self.db.execute(
            "UPDATE messages SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, message_id)
        )
        self.db.commit()
    
    def get_expired(self) -> List[Dict]:
        """Get messages past TTL"""
        return self.db.fetchall(
            """
            SELECT * FROM messages
            WHERE ttl_at IS NOT NULL
            AND ttl_at < CURRENT_TIMESTAMP
            AND status NOT IN ('completed', 'failed', 'ttl_expired')
            """
        )
    
    def list_messages(self, offset: int = 0, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        """List messages with pagination"""
        if status:
            return self.db.fetchall(
                """
                SELECT * FROM messages
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset)
            )
        else:
            return self.db.fetchall(
                """
                SELECT * FROM messages
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
    
    def count(self, status: Optional[str] = None) -> int:
        """Count messages, optionally filtered by status"""
        if status:
            row = self.db.fetchone("SELECT COUNT(*) as count FROM messages WHERE status = ?", (status,))
        else:
            row = self.db.fetchone("SELECT COUNT(*) as count FROM messages")
        return row['count'] if row else 0
    
    def list_all(self, limit: int = 100) -> List[Dict]:
        """List all messages (latest first)"""
        return self.db.fetchall(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    
    def delete(self, message_id: int):
        """Delete a message by ID"""
        self.db.execute(
            "DELETE FROM messages WHERE id = ?",
            (message_id,)
        )
        self.db.commit()


class DeliveryRepository(BaseRepository):
    """Repository for deliveries table"""
    
    def create(
        self,
        message_id: int,
        channel_id: int,
        destination: str,
        personalised_payload: Optional[str] = None,
        state: str = "queued",
        metadata_json: Optional[str] = None,
    ) -> int:
        """Create a new delivery"""
        # Insert delivery with metadata_json (column is ensured by migrations)
        cursor = self.db.execute(
            """
            INSERT INTO deliveries (
                message_id, channel_id, destination, personalised_payload, state, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, channel_id, destination, personalised_payload, state, metadata_json)
        )
        self.db.commit()
        delivery_id = cursor.lastrowid
        return delivery_id
    
    def get_by_id(self, delivery_id: int) -> Optional[Dict]:
        """Get delivery by ID"""
        return self.db.fetchone(
            "SELECT * FROM deliveries WHERE id = ?",
            (delivery_id,)
        )
    
    def get_by_message_id(self, message_id: int) -> List[Dict]:
        """Get all deliveries for a message, including channel labels."""
        return self.db.fetchall(
            """
            SELECT d.*, c.type as channel_type, c.name as channel_name
            FROM deliveries d
            LEFT JOIN channels c ON d.channel_id = c.id
            WHERE d.message_id = ?
            ORDER BY d.created_at
            """,
            (message_id,)
        )
    
    def update_state(
        self,
        delivery_id: int,
        state: str,
        last_error: Optional[str] = None,
        provider_tracking_id: Optional[str] = None,
    ):
        """Update delivery state"""
        updates = ["state = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [state]
        
        if last_error is not None:
            updates.append("last_error = ?")
            params.append(last_error)
        
        if provider_tracking_id is not None:
            updates.append("provider_tracking_id = ?")
            params.append(provider_tracking_id)
        
        # Set timestamps based on state
        if state == "sent":
            updates.append("sent_at = CURRENT_TIMESTAMP")
        elif state == "accepted":
            updates.append("accepted_at = CURRENT_TIMESTAMP")
        elif state == "delivered":
            updates.append("delivered_at = CURRENT_TIMESTAMP")
        elif state == "read":
            updates.append("read_at = CURRENT_TIMESTAMP")
        
        params.append(delivery_id)
        
        self.db.execute(
            f"UPDATE deliveries SET {', '.join(updates)} WHERE id = ?",
            tuple(params)
        )
        self.db.commit()
    
    def increment_attempt(self, delivery_id: int, next_action_at: Optional[datetime] = None):
        """Increment attempt counter and optionally set next_action_at"""
        if next_action_at:
            self.db.execute(
                "UPDATE deliveries SET attempt_no = attempt_no + 1, next_action_at = ? WHERE id = ?",
                (next_action_at, delivery_id)
            )
        else:
            self.db.execute(
                "UPDATE deliveries SET attempt_no = attempt_no + 1 WHERE id = ?",
                (delivery_id,)
            )
        self.db.commit()

    def set_next_action_at(self, delivery_id: int, next_action_at: Optional[datetime]):
        """Set or clear the next_action_at timestamp for a delivery."""
        self.db.execute(
            "UPDATE deliveries SET next_action_at = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (next_action_at, delivery_id),
        )
        self.db.commit()
    
    def update_payload(self, delivery_id: int, personalised_payload: str):
        """Update personalised payload for a delivery"""
        self.db.execute(
            "UPDATE deliveries SET personalised_payload = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (personalised_payload, delivery_id)
        )
        self.db.commit()

    def clear_payload(self, delivery_id: int):
        """Clear any persisted personalised payload for a delivery."""
        self.db.execute(
            "UPDATE deliveries SET personalised_payload = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (delivery_id,),
        )
        self.db.commit()
    
    def update_metadata(self, delivery_id: int, metadata_json: str):
        """Update delivery metadata"""
        # Check if metadata_json column exists
        try:
            self.db.execute(
                "UPDATE deliveries SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (metadata_json, delivery_id)
            )
            self.db.commit()
        except Exception as e:
            # Fallback if column doesn't exist (shouldn't happen, but handle gracefully)
            logger.warning(f"metadata_json column not found for delivery {delivery_id}: {e}")
    
    def list(self, state: Optional[str] = None, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """List deliveries, optionally filtered by state."""
        if state:
            return self.db.fetchall(
                """
                SELECT d.*, c.type as channel_type, c.name as channel_name
                FROM deliveries d
                LEFT JOIN channels c ON d.channel_id = c.id
                WHERE d.state = ?
                ORDER BY d.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (state, limit, offset)
            )
        else:
            return self.db.fetchall(
                """
                SELECT d.*, c.type as channel_type, c.name as channel_name
                FROM deliveries d
                LEFT JOIN channels c ON d.channel_id = c.id
                ORDER BY d.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
    
    def get_pending(self, limit: int = 1000) -> List[Dict]:
        """Get pending deliveries (queued/soft_failed/deferred with next_action_at <= now)."""
        return self.db.fetchall(
            """
            SELECT d.*, c.type as channel_type 
            FROM deliveries d
            LEFT JOIN channels c ON d.channel_id = c.id
            WHERE d.state IN ('queued', 'soft_failed', 'deferred')
            AND (d.next_action_at IS NULL OR d.next_action_at <= CURRENT_TIMESTAMP)
            -- Prioritize fresh first-attempt deliveries so retry backlogs do not
            -- starve new real-time traffic (e.g., loopback/API integration checks).
            ORDER BY
                COALESCE(d.attempt_no, 0) ASC,
                d.created_at DESC,
                d.id DESC
            LIMIT ?
            """,
            (limit,)
        )

    def count_pending_backlog(self) -> int:
        """Count queued backlog, including delayed soft-failed/deferred retries still waiting in DB."""
        row = self.db.fetchone(
            """
            SELECT COUNT(*) AS count
            FROM deliveries
            WHERE state IN ('queued', 'soft_failed', 'deferred')
            """
        )
        return int(row["count"] or 0) if row else 0
    
    def count_by_state(self, message_id: int) -> Dict[str, int]:
        """Count deliveries by state for a message"""
        rows = self.db.fetchall(
            """
            SELECT state, COUNT(*) as count
            FROM deliveries
            WHERE message_id = ?
            GROUP BY state
            """,
            (message_id,)
        )
        return {row["state"]: row["count"] for row in rows}
    
    def get_delivery_stats_by_message(self, message_id: int) -> Dict[str, int]:
        """Get delivery statistics for a message"""
        rows = self.db.fetchall(
            """
            SELECT state, COUNT(*) as count
            FROM deliveries
            WHERE message_id = ?
            GROUP BY state
            """,
            (message_id,)
        )
        return {row['state']: row['count'] for row in rows}
    
    def delete(self, delivery_id: int):
        """Delete a delivery by ID"""
        self.db.execute(
            "DELETE FROM deliveries WHERE id = ?",
            (delivery_id,)
        )
        self.db.commit()


class UserDestinationRepository(BaseRepository):
    """Repository for user_destinations table"""
    
    def create(
        self,
        user_id: int,
        channel_type: str,
        destination: str,
        verified: bool = False,
        is_primary: bool = False,
        metadata_json: Optional[str] = None,
    ) -> int:
        """Create a new user destination"""
        cursor = self.db.execute(
            """
            INSERT INTO user_destinations (
                user_id, channel_type, destination, verified, is_primary, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, channel_type, destination, verified, is_primary, metadata_json)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_user_id(self, user_id: int, channel_type: Optional[str] = None) -> List[Dict]:
        """Get all destinations for a user, optionally filtered by channel type"""
        if channel_type:
            return self.db.fetchall(
                """
                SELECT * FROM user_destinations
                WHERE user_id = ? AND channel_type = ?
                ORDER BY is_primary DESC, created_at
                """,
                (user_id, channel_type)
            )
        else:
            return self.db.fetchall(
                """
                SELECT * FROM user_destinations
                WHERE user_id = ?
                ORDER BY channel_type, is_primary DESC, created_at
                """,
                (user_id,)
            )
    
    def get_primary(self, user_id: int, channel_type: str) -> Optional[Dict]:
        """Get primary destination for a user and channel type"""
        return self.db.fetchone(
            """
            SELECT * FROM user_destinations
            WHERE user_id = ? AND channel_type = ? AND is_primary = 1
            LIMIT 1
            """,
            (user_id, channel_type)
        )
    
    def set_primary(self, destination_id: int, user_id: int, channel_type: str):
        """Set a destination as primary (unset others for same user/channel)"""
        # Unset all primary destinations for this user/channel
        self.db.execute(
            """
            UPDATE user_destinations
            SET is_primary = 0
            WHERE user_id = ? AND channel_type = ? AND is_primary = 1
            """,
            (user_id, channel_type)
        )
        # Set this one as primary
        self.db.execute(
            """
            UPDATE user_destinations
            SET is_primary = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (destination_id, user_id)
        )
        self.db.commit()
    
    def delete(self, destination_id: int, user_id: int):
        """Delete a destination"""
        self.db.execute(
            "DELETE FROM user_destinations WHERE id = ? AND user_id = ?",
            (destination_id, user_id)
        )
        self.db.commit()
    
    def get_by_id(self, destination_id: int) -> Optional[Dict]:
        """Get destination by ID"""
        return self.db.fetchone(
            "SELECT * FROM user_destinations WHERE id = ?",
            (destination_id,)
        )


class UserKeywordRepository(BaseRepository):
    """Repository for user_keywords table"""
    
    def add(self, user_id: int, keyword: str):
        """Add a keyword to a user"""
        try:
            cursor = self.db.execute(
                "INSERT INTO user_keywords (user_id, keyword) VALUES (?, ?)",
                (user_id, keyword)
            )
            self.db.commit()
            return cursor.lastrowid
        except SQLAlchemyIntegrityError:
            # Keyword already exists (UNIQUE constraint)
            return None
    
    def remove(self, user_id: int, keyword: str):
        """Remove a keyword from a user"""
        self.db.execute(
            "DELETE FROM user_keywords WHERE user_id = ? AND keyword = ?",
            (user_id, keyword)
        )
        self.db.commit()
    
    def get_by_user_id(self, user_id: int) -> List[Dict]:
        """Get all keywords for a user"""
        return self.db.fetchall(
            "SELECT * FROM user_keywords WHERE user_id = ? ORDER BY keyword",
            (user_id,)
        )
    
    def get_by_keyword(self, keyword: str) -> List[Dict]:
        """Get all users with a specific keyword"""
        return self.db.fetchall(
            "SELECT * FROM user_keywords WHERE keyword = ?",
            (keyword,)
        )


class ChannelRepository(BaseRepository):
    """Repository for channels table"""
    
    def create(
        self,
        name: str,
        channel_type: str,
        enabled: bool = True,
        config_json: Optional[str] = None,
        limits_json: Optional[str] = None,
    ) -> int:
        """Create a new channel"""
        cursor = self.db.execute(
            """
            INSERT INTO channels (name, type, enabled, config_json, limits_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, channel_type, enabled, config_json, limits_json)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_id(self, channel_id: int) -> Optional[Dict]:
        """Get channel by ID"""
        return self.db.fetchone(
            "SELECT * FROM channels WHERE id = ?",
            (channel_id,)
        )
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get channel by name"""
        return self.db.fetchone(
            "SELECT * FROM channels WHERE name = ?",
            (name,)
        )
    
    def get_by_type(self, channel_type: str) -> List[Dict]:
        """Get all channels of a specific type"""
        return self.db.fetchall(
            "SELECT * FROM channels WHERE type = ?",
            (channel_type,)
        )

    def count_deliveries(self, channel_id: int) -> int:
        """Count deliveries that reference a channel."""
        row = self.db.fetchone(
            "SELECT COUNT(*) AS count FROM deliveries WHERE channel_id = ?",
            (channel_id,)
        )
        return int((row or {}).get("count") or 0)
    
    def list_all(self, enabled_only: bool = False) -> List[Dict]:
        """List all channels"""
        if enabled_only:
            return self.db.fetchall(
                "SELECT * FROM channels WHERE enabled = 1 ORDER BY name"
            )
        return self.db.fetchall(
            "SELECT * FROM channels ORDER BY name"
        )
    
    def update(self, channel_id: int, updates: Dict[str, Any]):
        """Update channel fields"""
        fields = []
        params = []
        
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            params.append(value)
        
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(channel_id)
        
        self.db.execute(
            f"UPDATE channels SET {', '.join(fields)} WHERE id = ?",
            tuple(params)
        )
        self.db.commit()

    def delete(self, channel_id: int):
        """Delete channel by ID"""
        self.db.execute(
            "DELETE FROM channels WHERE id = ?",
            (channel_id,)
        )
        self.db.commit()
    
    def increment_error_count(self, channel_id: int):
        """Increment error count"""
        self.db.execute(
            """
            UPDATE channels
            SET error_count = error_count + 1,
                last_error_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (channel_id,)
        )
        self.db.commit()
    
    def reset_error_count(self, channel_id: int):
        """Reset error count"""
        self.db.execute(
            """
            UPDATE channels
            SET error_count = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (channel_id,)
        )
        self.db.commit()


class ReceiptRepository(BaseRepository):
    """Repository for receipts table"""
    
    def create(
        self,
        delivery_id: int,
        provider_event: str,
        status: str,
        raw_data: str,
        signature_ok: bool = False,
    ) -> int:
        """Create a new receipt"""
        cursor = self.db.execute(
            """
            INSERT INTO receipts (
                delivery_id, provider_event, status, raw_data, signature_ok
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (delivery_id, provider_event, status, raw_data, signature_ok)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_delivery_id(self, delivery_id: int) -> List[Dict]:
        """Get all receipts for a delivery"""
        return self.db.fetchall(
            "SELECT * FROM receipts WHERE delivery_id = ? ORDER BY received_at",
            (delivery_id,)
        )
    
    def mark_processed(self, receipt_id: int):
        """Mark receipt as processed"""
        self.db.execute(
            "UPDATE receipts SET processed = 1 WHERE id = ?",
            (receipt_id,)
        )
        self.db.commit()
    
    def delete(self, receipt_id: int):
        """Delete a receipt by ID"""
        self.db.execute(
            "DELETE FROM receipts WHERE id = ?",
            (receipt_id,)
        )
        self.db.commit()


class UserRepository(BaseRepository):
    """Repository for users table"""
    
    def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        role: str = "viewer",
        display_name: Optional[str] = None,
        user_type: str = "real",
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> int:
        """Create a new user and automatically create user_destination for email"""
        cursor = self.db.execute(
            """
            INSERT INTO users (
                username, email, password_hash, role, display_name,
                user_type, language, preferred_channel, content_style, timezone
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, email, password_hash, role, display_name,
             user_type, language, preferred_channel, content_style, timezone)
        )
        self.db.commit()  # Commit user creation FIRST
        user_id = cursor.lastrowid
        
        # Automatically create user_destination for email (smtp channel)
        if email:
            try:
                self.db.execute(
                    """
                    INSERT INTO user_destinations (user_id, channel_type, destination)
                    VALUES (?, 'smtp', ?)
                    """,
                    (user_id, email)
                )
                self.db.commit()  # Commit user_destination immediately
            except Exception:
                # Ignore if destination already exists (e.g., from a previous user)
                pass
        
        return user_id
    
    def get_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        return self.db.fetchone(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        return self.db.fetchone(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )
    
    def get_by_display_name(self, display_name: str) -> Optional[Dict]:
        """Get user by display name"""
        return self.db.fetchone(
            "SELECT * FROM users WHERE display_name = ?",
            (display_name,)
        )
    
    def get_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        return self.db.fetchone(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
    
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Search users by username, email, or display_name"""
        search_term = f"%{query}%"
        return self.db.fetchall(
            """
            SELECT * FROM users
            WHERE username LIKE ? OR email LIKE ? OR display_name LIKE ?
            ORDER BY username
            LIMIT ?
            """,
            (search_term, search_term, search_term, limit)
        )
    
    def list_all(self, limit: int = 1000) -> List[Dict]:
        """List all users"""
        return self.db.fetchall(
            "SELECT * FROM users ORDER BY username LIMIT ?",
            (limit,)
        )
    
    def update_preferences(
        self,
        user_id: int,
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        timezone: Optional[str] = None,
    ):
        """Update user preferences"""
        updates = []
        params = []
        
        if language is not None:
            updates.append("language = ?")
            params.append(language)
        if preferred_channel is not None:
            updates.append("preferred_channel = ?")
            params.append(preferred_channel)
        if content_style is not None:
            updates.append("content_style = ?")
            params.append(content_style)
        if timezone is not None:
            updates.append("timezone = ?")
            params.append(timezone)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            self.db.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            self.db.commit()

    def delete(self, user_id: int):
        """
        Delete a user and related records.
        Used by API cleanup flows and tests (via API endpoints).
        """
        # Remove relationships first
        self.db.execute("DELETE FROM user_keywords WHERE user_id = ?", (user_id,))
        self.db.execute("DELETE FROM user_destinations WHERE user_id = ?", (user_id,))
        self.db.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
        self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.db.commit()

    def set_enabled(self, user_id: int, enabled: bool) -> None:
        """Enable or disable a user."""
        self.db.execute(
            "UPDATE users SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (1 if enabled else 0, user_id),
        )
        self.db.commit()

    def clear_preferences(self, user_id: int) -> None:
        """Clear nullable preference fields for a user."""
        self.db.execute(
            """
            UPDATE users
            SET language = NULL,
                preferred_channel = NULL,
                content_style = NULL,
                timezone = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )
        self.db.commit()

    def update_last_login(self, user_id: int):
        """Update last login timestamp"""
        self.db.execute(
            """
            UPDATE users
            SET last_login_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,)
        )
        self.db.commit()


class TemplateRepository(BaseRepository):
    """Repository for templates table"""
    
    def create(
        self,
        name: str,
        format: str,
        body: str,
        version: int = 1,
        validators_json: Optional[str] = None,
    ) -> int:
        """Create a new template"""
        cursor = self.db.execute(
            """
            INSERT INTO templates (name, format, body, version, validators_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, format, body, version, validators_json)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_id(self, template_id: int) -> Optional[Dict]:
        """Get template by ID"""
        return self.db.fetchone(
            "SELECT * FROM templates WHERE id = ?",
            (template_id,)
        )
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get template by name"""
        return self.db.fetchone(
            "SELECT * FROM templates WHERE name = ?",
            (name,)
        )


class AuditEventRepository(BaseRepository):
    """Repository for audit_events table"""
    
    def create(
        self,
        kind: str,
        actor: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        details_json: Optional[str] = None,
    ) -> int:
        """Create a new audit event
        
        Note: Schema uses ref_type, ref_id, data_json (not target_type, target_id, details_json)
        """
        cursor = self.db.execute(
            """
            INSERT INTO audit_events (kind, actor, ref_type, ref_id, data_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (kind, actor, target_type, target_id, details_json)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def list_events(
        self,
        kind: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict]:
        """List audit events"""
        if kind:
            return self.db.fetchall(
                """
                SELECT * FROM audit_events
                WHERE kind = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (kind, limit, offset)
            )
        else:
            return self.db.fetchall(
                """
                SELECT * FROM audit_events
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )


class GroupRepository(BaseRepository):
    """Repository for groups table"""
    
    def create(
        self,
        name: str,
        description: Optional[str] = None,
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        enabled: bool = True,
    ) -> int:
        """Create a new group"""
        cursor = self.db.execute(
            """
            INSERT INTO groups (name, description, language, preferred_channel, content_style, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, description, language, preferred_channel, content_style, enabled)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_id(self, group_id: int) -> Optional[Dict]:
        """Get group by ID"""
        return self.db.fetchone(
            "SELECT * FROM groups WHERE id = ?",
            (group_id,)
        )
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get group by name"""
        return self.db.fetchone(
            "SELECT * FROM groups WHERE name = ?",
            (name,)
        )
    
    def list_all(self, enabled_only: bool = False) -> List[Dict]:
        """List all groups"""
        if enabled_only:
            return self.db.fetchall(
                "SELECT * FROM groups WHERE enabled = 1 ORDER BY name"
            )
        return self.db.fetchall(
            "SELECT * FROM groups ORDER BY name"
        )
    
    def update(
        self,
        group_id: int,
        description: Optional[str] = None,
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        """Update group"""
        updates = []
        params = []
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if language is not None:
            updates.append("language = ?")
            params.append(language)
        if preferred_channel is not None:
            updates.append("preferred_channel = ?")
            params.append(preferred_channel)
        if content_style is not None:
            updates.append("content_style = ?")
            params.append(content_style)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(group_id)
            self.db.execute(
                f"UPDATE groups SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            self.db.commit()

    def delete(self, group_id: int):
        """Delete group by ID"""
        self.db.execute(
            "DELETE FROM groups WHERE id = ?",
            (group_id,)
        )
        self.db.commit()


class GroupMemberRepository(BaseRepository):
    """Repository for group_members table"""
    
    def add_member(self, group_id: int, user_id: int, role: str = "member") -> int:
        """Add a user to a group"""
        try:
            cursor = self.db.execute(
                "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
                (group_id, user_id, role)
            )
            self.db.commit()
            return cursor.lastrowid
        except SQLAlchemyIntegrityError:
            # Member already exists (UNIQUE constraint)
            return None
    
    def remove_member(self, group_id: int, user_id: int):
        """Remove a user from a group"""
        self.db.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id)
        )
        self.db.commit()

    def remove_group_members(self, group_id: int):
        """Remove all members from a group"""
        self.db.execute(
            "DELETE FROM group_members WHERE group_id = ?",
            (group_id,)
        )
        self.db.commit()
    
    def remove_member_by_id(self, member_id: int):
        """Remove a group member by member ID"""
        self.db.execute(
            "DELETE FROM group_members WHERE id = ?",
            (member_id,)
        )
        self.db.commit()
    
    def get_group_members(self, group_id: int) -> List[Dict]:
        """Get all members of a group"""
        return self.db.fetchall(
            """
            SELECT gm.*, u.username, u.email, u.display_name
            FROM group_members gm
            JOIN users u ON gm.user_id = u.id
            WHERE gm.group_id = ?
            ORDER BY u.username
            """,
            (group_id,)
        )
    
    def get_user_groups(self, user_id: int) -> List[Dict]:
        """Get all groups a user belongs to"""
        return self.db.fetchall(
            """
            SELECT g.*, gm.role
            FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            WHERE gm.user_id = ?
            ORDER BY g.name
            """,
            (user_id,)
        )
    
    def update_role(self, group_id: int, user_id: int, role: str):
        """Update a member's role"""
        self.db.execute(
            "UPDATE group_members SET role = ? WHERE group_id = ? AND user_id = ?",
            (role, group_id, user_id)
        )
        self.db.commit()


class GroupKeywordRepository(BaseRepository):
    """Repository for group_keywords table"""
    
    def add(self, group_id: int, keyword: str):
        """Add a keyword to a group"""
        try:
            cursor = self.db.execute(
                "INSERT INTO group_keywords (group_id, keyword) VALUES (?, ?)",
                (group_id, keyword)
            )
            self.db.commit()
            return cursor.lastrowid
        except SQLAlchemyIntegrityError:
            # Keyword already exists (UNIQUE constraint)
            return None
    
    def remove(self, group_id: int, keyword: str):
        """Remove a keyword from a group"""
        self.db.execute(
            "DELETE FROM group_keywords WHERE group_id = ? AND keyword = ?",
            (group_id, keyword)
        )
        self.db.commit()

    def remove_group_keywords(self, group_id: int):
        """Remove all keywords from a group"""
        self.db.execute(
            "DELETE FROM group_keywords WHERE group_id = ?",
            (group_id,)
        )
        self.db.commit()
    
    def get_by_group_id(self, group_id: int) -> List[Dict]:
        """Get all keywords for a group"""
        return self.db.fetchall(
            "SELECT * FROM group_keywords WHERE group_id = ? ORDER BY keyword",
            (group_id,)
        )

class LLMPromptRepository(BaseRepository):
    """Repository for llm_prompts table"""
    
    def create(
        self,
        name: str,
        prompt_text: str,
        channel_type: Optional[str] = None,
        group_id: Optional[int] = None,
        language: Optional[str] = None,
        keyword: Optional[str] = None,
        variables_json: Optional[str] = None,
        priority: int = 0,
        enabled: bool = True,
    ) -> int:
        """Create a new LLM prompt"""
        cursor = self.db.execute(
            """
            INSERT INTO llm_prompts (
                name, channel_type, group_id, language, keyword,
                prompt_text, variables_json, priority, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, channel_type, group_id, language, keyword,
             prompt_text, variables_json, priority, enabled)
        )
        self.db.commit()
        return cursor.lastrowid
    
    def get_by_id(self, prompt_id: int) -> Optional[Dict]:
        """Get prompt by ID"""
        return self.db.fetchone(
            "SELECT * FROM llm_prompts WHERE id = ?",
            (prompt_id,)
        )
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get prompt by name"""
        return self.db.fetchone(
            "SELECT * FROM llm_prompts WHERE name = ? AND enabled = 1 ORDER BY priority DESC, id DESC LIMIT 1",
            (name,)
        )
    
    def find_best_match(
        self,
        channel_type: Optional[str] = None,
        group_id: Optional[int] = None,
        language: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find the best matching prompt based on priority and specificity.
        """
        conditions = ["enabled = 1"]
        params = []
        
        if channel_type:
            conditions.append("(channel_type = ? OR channel_type IS NULL)")
            params.append(channel_type)
        else:
            conditions.append("channel_type IS NULL")
        if group_id:
            conditions.append("(group_id = ? OR group_id IS NULL)")
            params.append(group_id)
        else:
            conditions.append("group_id IS NULL")
        if language:
            conditions.append("(language = ? OR language IS NULL)")
            params.append(language)
        else:
            conditions.append("language IS NULL")
        if keyword:
            conditions.append("(keyword = ? OR keyword IS NULL)")
            params.append(keyword)
        else:
            conditions.append("keyword IS NULL")
        
        # Calculate specificity score - explicit matches score higher
        query = """
            SELECT *,
                (CASE WHEN channel_type = ? THEN 8 WHEN channel_type IS NULL THEN 0 ELSE 0 END) +
                (CASE WHEN group_id = ? THEN 4 WHEN group_id IS NULL THEN 0 ELSE 0 END) +
                (CASE WHEN language = ? THEN 2 WHEN language IS NULL THEN 0 ELSE 0 END) +
                (CASE WHEN keyword = ? THEN 1 WHEN keyword IS NULL THEN 0 ELSE 0 END)
                as specificity_score
            FROM llm_prompts
            WHERE """ + " AND ".join(conditions) + """
            ORDER BY specificity_score DESC, priority DESC, id DESC
            LIMIT 1
        """
        
        query_params = [channel_type, group_id, language, keyword] + params
        return self.db.fetchone(query, tuple(query_params))
    
    def list_all(
        self,
        channel_type: Optional[str] = None,
        group_id: Optional[int] = None,
        enabled_only: bool = True,
    ) -> List[Dict]:
        """List prompts with optional filters"""
        conditions = []
        params = []
        
        if channel_type:
            conditions.append("channel_type = ?")
            params.append(channel_type)
        if group_id:
            conditions.append("group_id = ?")
            params.append(group_id)
        if enabled_only:
            conditions.append("enabled = 1")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        return self.db.fetchall(
            f"""
            SELECT * FROM llm_prompts
            {where_clause}
            ORDER BY priority DESC, name
            """,
            tuple(params) if params else None
        )
    
    def update(
        self,
        prompt_id: int,
        name: Optional[str] = None,
        prompt_text: Optional[str] = None,
        variables_json: Optional[str] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        """Update prompt"""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if prompt_text is not None:
            updates.append("prompt_text = ?")
            params.append(prompt_text)
        if variables_json is not None:
            updates.append("variables_json = ?")
            params.append(variables_json)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(enabled)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(prompt_id)
            self.db.execute(
                f"UPDATE llm_prompts SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            self.db.commit()
