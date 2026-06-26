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
Description: Audit Signer - Cryptographic signing of audit entries

Related Requirements: NF1.7
Related Tasks: T38
Related Architecture: SE1.3
Related Tests: ST1.12

Recent Changes (max 10):
- 2026-02-24: Removed implicit built-in signing key path and aligned signing primitives with cloud_dog_logging
**************************************************
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from cloud_dog_logging.signing import HMACSigner

from ...utils.logger import get_logger

logger = get_logger(__name__)


class AuditSigner:
    """Cryptographic signer for audit entries."""

    def __init__(self, secret_key: Optional[str] = None):
        """Initialise audit signer with an explicit non-empty secret key."""
        if not secret_key or not str(secret_key).strip():
            raise ValueError(
                "Audit signing key is required; configure log.audit.signing.key before enabling signing"
            )

        self.secret_key = str(secret_key).encode("utf-8")
        self._chain_signer = HMACSigner(str(secret_key))
        logger.info("AuditSigner initialized")

    def sign_audit_entry(self, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sign an audit entry and append metadata fields."""
        canonical = self._canonicalize(audit_data)
        signature = hmac.new(self.secret_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

        signed_entry = audit_data.copy()
        signed_entry["signature"] = signature
        signed_entry["signed_at"] = datetime.now().isoformat()
        return signed_entry

    def verify_audit_entry(self, audit_entry: Dict[str, Any]) -> bool:
        """Verify an audit entry signature."""
        if "signature" not in audit_entry:
            return False

        signature = audit_entry.pop("signature")
        signed_at = audit_entry.pop("signed_at", None)

        canonical = self._canonicalize(audit_entry)
        expected_signature = hmac.new(self.secret_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

        audit_entry["signature"] = signature
        if signed_at:
            audit_entry["signed_at"] = signed_at

        return hmac.compare_digest(signature, expected_signature)

    def _canonicalize(self, data: Dict[str, Any]) -> str:
        """Create canonical representation of data for signing."""
        clean_data = {k: v for k, v in data.items() if k not in ["signature", "signed_at"]}
        return json.dumps(clean_data, sort_keys=True, default=str)

    def export_audit_trail(
        self,
        audit_entries: List[Dict[str, Any]],
        include_signatures: bool = True,
    ) -> Dict[str, Any]:
        """Export audit trail with signature verification summary."""
        verified_count = 0
        invalid_count = 0

        for entry in audit_entries:
            if self.verify_audit_entry(entry.copy()):
                verified_count += 1
            else:
                invalid_count += 1

        return {
            "export_date": datetime.now().isoformat(),
            "total_entries": len(audit_entries),
            "verified_entries": verified_count,
            "invalid_entries": invalid_count,
            "entries": audit_entries
            if include_signatures
            else [{k: v for k, v in e.items() if k not in ["signature", "signed_at"]} for e in audit_entries],
        }
