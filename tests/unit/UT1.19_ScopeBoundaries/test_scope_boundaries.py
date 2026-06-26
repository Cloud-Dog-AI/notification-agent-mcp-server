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
UT1.19: Scope boundary guardrails (SV1.1, SV1.2, SV1.3).

These tests keep high-level scope promises explicit:
- Expected server surfaces and in-scope channels exist.
- Explicitly out-of-scope features are not accidentally introduced.
"""

from __future__ import annotations
import pytest

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-019")


def test_ut119_server_surfaces_exist() -> None:
    expected = [
        SRC_ROOT / "servers" / "api" / "api_server.py",
        SRC_ROOT / "servers" / "mcp" / "mcp_server.py",
        SRC_ROOT / "servers" / "a2a" / "a2a_server.py",
        SRC_ROOT / "servers" / "web" / "web_server.py",
    ]
    missing = [p.as_posix() for p in expected if not p.exists()]
    assert not missing, "Missing expected server surfaces:\n" + "\n".join(missing)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-019")


def test_ut119_in_scope_channel_adapters_exist() -> None:
    expected = [
        SRC_ROOT / "adapters" / "smtp_adapter.py",
        SRC_ROOT / "adapters" / "sms_adapter.py",
        SRC_ROOT / "adapters" / "whatsapp_adapter.py",
        SRC_ROOT / "adapters" / "chat_adapter.py",
    ]
    missing = [p.as_posix() for p in expected if not p.exists()]
    assert not missing, "Missing expected in-scope channel adapters:\n" + "\n".join(missing)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-019")


def test_ut119_out_of_scope_features_absent() -> None:
    disallowed_module_terms = ("apns", "fcm", "firebase")
    disallowed_tenancy_terms = ("tenant_id", "multitenant", "multi_tenant")

    module_hits = []
    tenancy_hits = []
    for py in SRC_ROOT.rglob("*.py"):
        rel = py.relative_to(PROJECT_ROOT).as_posix()
        lower_rel = rel.lower()
        if any(term in lower_rel for term in disallowed_module_terms):
            module_hits.append(rel)
            continue

        text = py.read_text(encoding="utf-8")
        for term in disallowed_tenancy_terms:
            if term in text:
                tenancy_hits.append(f"{rel}: contains '{term}'")

    assert not module_hits, (
        "Out-of-scope push adapter/module names detected:\n" + "\n".join(module_hits)
    )
    assert not tenancy_hits, (
        "Out-of-scope multi-tenant constructs detected:\n" + "\n".join(tenancy_hits)
    )

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.fast]

