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
Description: Audit Exporter - Export and verification of audit trails

Related Requirements: NF1.7
Related Tasks: T38
Related Architecture: SE1.3
Related Tests: ST1.12

Recent Changes (max 10):
- 2026-02-24: Removed implicit signer autoconfiguration to enforce explicit signing key configuration
**************************************************
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

from ...utils.logger import get_logger
from .signer import AuditSigner

_fs = _PlatformLocalStorage(root_path="/")

logger = get_logger(__name__)


class AuditExporter:
    """Export and verify audit trails."""

    def __init__(self, signer: Optional[AuditSigner] = None):
        self.signer = signer
        logger.info("AuditExporter initialized")

    def export_audit_trail(
        self,
        audit_entries: List[Dict[str, Any]],
        output_path: Optional[str] = None,
        include_signatures: bool = True,
        verify_signatures: bool = True,
    ) -> Dict[str, Any]:
        """Export audit trail to file or return as dict."""
        verified_count = 0
        invalid_count = 0

        if verify_signatures and self.signer:
            for entry in audit_entries:
                if self.signer.verify_audit_entry(entry.copy()):
                    verified_count += 1
                else:
                    invalid_count += 1

        export = {
            "export_date": datetime.now().isoformat(),
            "export_version": "1.0",
            "total_entries": len(audit_entries),
            "verified_entries": verified_count if verify_signatures and self.signer else None,
            "invalid_entries": invalid_count if verify_signatures and self.signer else None,
            "entries": audit_entries
            if include_signatures
            else [{k: v for k, v in e.items() if k not in ["signature", "signed_at"]} for e in audit_entries],
        }

        if output_path:
            import os as _os
            export_bytes = json.dumps(export, indent=2, default=str).encode("utf-8")
            parent_dir = _os.path.dirname(output_path)
            if parent_dir:
                _fs.create_dir(parent_dir)
            _fs.write_bytes(output_path, export_bytes)
            logger.info(f"Audit trail exported to {output_path}")

        return export

    def verify_audit_trail(self, audit_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Verify all signatures in audit trail."""
        if not self.signer:
            raise ValueError("AuditExporter.verify_audit_trail requires an AuditSigner")

        verified = []
        invalid = []

        for entry in audit_entries:
            entry_copy = entry.copy()
            if self.signer.verify_audit_entry(entry_copy):
                verified.append(entry)
            else:
                invalid.append(entry)

        return {
            "total": len(audit_entries),
            "verified": len(verified),
            "invalid": len(invalid),
            "verification_rate": len(verified) / len(audit_entries) if audit_entries else 0,
            "invalid_entries": invalid,
        }
