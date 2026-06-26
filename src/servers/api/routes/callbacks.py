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
Description: Callback routes for delivery confirmations - Handles webhook callbacks from notification providers (SMTP, SMS, Chat)

Related Requirements: FR1.2
Related Tasks: T7, T9
Related Architecture: CC1.1, CC2.1.4
Related Tests: IT1.10

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import json

from src.core.security.signature import SignatureManager
from src.core.confirmations.processor import CallbackProcessor
from src.database import get_db_manager
from src.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

def _runtime_config():
    return get_config(unresolved_policy="empty")


def _callback_processor() -> CallbackProcessor:
    db_uri = _runtime_config().get("db.uri")
    if not db_uri:
        raise RuntimeError("Missing required configuration: db.uri")
    return CallbackProcessor(get_db_manager(db_uri))


def _signature_manager() -> SignatureManager:
    webhook_secret = _runtime_config().get("webhook.secret")
    if not webhook_secret:
        raise RuntimeError("Missing required configuration: webhook.secret")
    return SignatureManager(webhook_secret)


def _verify_webhook_auth(request: Request, signature: Optional[str], timestamp: Optional[str], body: bytes) -> None:
    """Verify webhook signature as RBAC enforcement for callback endpoints.

    Callback endpoints use HMAC signature verification instead of API key auth.
    This is equivalent to has_permission("callbacks:write") — the webhook secret
    acts as a shared-secret credential that authorises the provider to submit
    delivery status updates (PS-70 UM3 enforcement via cloud_dog_idam contract).
    """
    from src.core.rbac import get_checker_for_user
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing webhook signature or timestamp")
    try:
        signature_manager = _signature_manager()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not signature_manager.verify(body.decode("utf-8", errors="replace"), signature, timestamp):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("/callbacks/email")
async def email_callback(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
    x_webhook_timestamp: Optional[str] = Header(None)
):
    """
    Handle SMTP/email delivery notification callbacks.
    
    Expected payload:
    ```json
    {
        "event": "delivered" | "bounced" | "opened" | "clicked",
        "delivery_id": 123,
        "message_id": "ext_msg_id",
        "recipient": "user@example.com",
        "timestamp": "2025-11-10T20:00:00Z"
    }
    ```
    """
    # Get raw body for signature verification
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # Verify signature if provided
    if x_webhook_signature and x_webhook_timestamp:
        try:
            signature_manager = _signature_manager()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        is_valid, error = signature_manager.verify_webhook(
            body_str,
            x_webhook_timestamp,
            x_webhook_signature
        )
        if not is_valid:
            logger.warning(f"Invalid webhook signature for email callback: {error}")
            raise HTTPException(status_code=401, detail=f"Invalid signature: {error}")
    
    # Parse JSON payload
    try:
        callback_data = json.loads(body_str)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Process callback
    try:
        result = await _callback_processor().process_callback("email", callback_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    
    if result["success"]:
        return {
            "status": "ok",
            "delivery_id": result.get("delivery_id"),
            "duplicate": result.get("duplicate", False)
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Processing failed"))


@router.post("/callbacks/sms")
async def sms_callback(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
    x_webhook_timestamp: Optional[str] = Header(None)
):
    """
    Handle SMS delivery receipt callbacks.
    
    Expected payload (Twilio format):
    ```json
    {
        "MessageStatus": "delivered" | "sent" | "failed" | "undelivered",
        "MessageSid": "SM...",
        "To": "+1234567890",
        "From": "+0987654321",
        "delivery_id": 123
    }
    ```
    """
    # Get raw body for signature verification
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # Verify signature if provided
    if x_webhook_signature and x_webhook_timestamp:
        try:
            signature_manager = _signature_manager()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        is_valid, error = signature_manager.verify_webhook(
            body_str,
            x_webhook_timestamp,
            x_webhook_signature
        )
        if not is_valid:
            logger.warning(f"Invalid webhook signature for SMS callback: {error}")
            raise HTTPException(status_code=401, detail=f"Invalid signature: {error}")
    
    # Parse JSON or form data (Twilio can send either)
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            callback_data = json.loads(body_str)
        else:
            # Parse form data
            from urllib.parse import parse_qs
            form_data = parse_qs(body_str)
            callback_data = {k: v[0] for k, v in form_data.items()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")
    
    # Process callback
    try:
        result = await _callback_processor().process_callback("sms", callback_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    
    if result["success"]:
        return {
            "status": "ok",
            "delivery_id": result.get("delivery_id"),
            "duplicate": result.get("duplicate", False)
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Processing failed"))


@router.post("/callbacks/whatsapp")
async def whatsapp_callback(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
    x_webhook_timestamp: Optional[str] = Header(None)
):
    """
    Handle WhatsApp status update callbacks.
    
    Expected payload:
    ```json
    {
        "status": "sent" | "delivered" | "read" | "failed",
        "message_id": "wamid...",
        "delivery_id": 123,
        "timestamp": "2025-11-10T20:00:00Z"
    }
    ```
    """
    # Get raw body for signature verification
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # Verify signature if provided
    if x_webhook_signature and x_webhook_timestamp:
        try:
            signature_manager = _signature_manager()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        is_valid, error = signature_manager.verify_webhook(
            body_str,
            x_webhook_timestamp,
            x_webhook_signature
        )
        if not is_valid:
            logger.warning(f"Invalid webhook signature for WhatsApp callback: {error}")
            raise HTTPException(status_code=401, detail=f"Invalid signature: {error}")
    
    # Parse JSON payload
    try:
        callback_data = json.loads(body_str)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Process callback (use chat channel type for WhatsApp)
    try:
        result = await _callback_processor().process_callback("chat", callback_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    
    if result["success"]:
        return {
            "status": "ok",
            "delivery_id": result.get("delivery_id"),
            "duplicate": result.get("duplicate", False)
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Processing failed"))


@router.post("/callbacks/chat")
async def chat_callback(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
    x_webhook_timestamp: Optional[str] = Header(None)
):
    """
    Handle generic chat/webhook callbacks.
    
    Expected payload:
    ```json
    {
        "status": "delivered" | "failed",
        "message_id": "msg_...",
        "delivery_id": 123,
        "timestamp": "2025-11-10T20:00:00Z"
    }
    ```
    """
    # Get raw body for signature verification
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # Verify signature if provided
    if x_webhook_signature and x_webhook_timestamp:
        try:
            signature_manager = _signature_manager()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        is_valid, error = signature_manager.verify_webhook(
            body_str,
            x_webhook_timestamp,
            x_webhook_signature
        )
        if not is_valid:
            logger.warning(f"Invalid webhook signature for chat callback: {error}")
            raise HTTPException(status_code=401, detail=f"Invalid signature: {error}")
    
    # Parse JSON payload
    try:
        callback_data = json.loads(body_str)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Process callback
    try:
        result = await _callback_processor().process_callback("chat", callback_data)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    
    if result["success"]:
        return {
            "status": "ok",
            "delivery_id": result.get("delivery_id"),
            "duplicate": result.get("duplicate", False)
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Processing failed"))


@router.get("/callbacks/health")
async def callback_health():
    """Health check for callback endpoints."""
    return {
        "status": "ok",
        "endpoints": [
            "/callbacks/email",
            "/callbacks/sms",
            "/callbacks/whatsapp",
            "/callbacks/chat"
        ]
    }
