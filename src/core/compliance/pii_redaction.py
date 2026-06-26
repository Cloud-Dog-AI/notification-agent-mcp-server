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
Description: PII Redaction - Minimise PII in stored data

Related Requirements: NF1.4, NF1.8
Related Tasks: T35, T39
Related Architecture: SE1.4
Related Tests: ST1.10, ST1.13

Recent Changes (max 10):
- 2026-02-24: Migrated PII redaction internals to cloud_dog_logging.redaction.RedactionEngine
**************************************************
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from cloud_dog_logging.redaction import RedactionEngine

from ...utils.logger import get_logger

logger = get_logger(__name__)


class PIIRedactor:
    """PII redaction and minimisation."""

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b")

    def __init__(self, hash_salt: Optional[str] = None):
        self.hash_salt = hash_salt or "default_salt"
        self._engine = RedactionEngine()
        logger.info("PIIRedactor initialized")

    def redact_text(self, text: str, replace_with: str = "[REDACTED]") -> str:
        """Redact PII from free text."""
        result = text
        result = self.EMAIL_PATTERN.sub(replace_with, result)
        result = self.PHONE_PATTERN.sub(replace_with, result)
        result = self.SSN_PATTERN.sub(replace_with, result)
        result = self.CREDIT_CARD_PATTERN.sub(replace_with, result)
        return result

    def hash_value(self, value: str) -> str:
        """Hash a value for storage."""
        combined = f"{value}{self.hash_salt}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def redact_dict(self, data: Dict[str, Any], pii_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Redact PII from dictionary values."""
        if pii_fields is None:
            pii_fields = ["email", "phone", "ssn", "credit_card", "password", "api_key", "secret"]

        result = self._engine.redact(data)

        for field in pii_fields:
            if field in result:
                value = result[field]
                if isinstance(value, str) and value != "***REDACTED***":
                    result[field] = self.hash_value(value)
                elif value != "***REDACTED***":
                    result[field] = "[REDACTED]"

        for key, value in list(result.items()):
            if isinstance(value, str) and key not in pii_fields:
                result[key] = self.redact_text(value)

        return result
