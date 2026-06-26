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

"""QT1.4: Requirements/tests traceability checks."""

from __future__ import annotations
import pytest

from pathlib import Path
import re


_REQ_RE = re.compile(r"\b(?:SV|BO|BR|FR|UC|CS|NF)\d+\.\d+\b")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_requirements_document_has_ids(project_root: Path) -> None:
    req_text = _read(project_root / "docs" / "REQUIREMENTS.md")
    req_ids = sorted(set(_REQ_RE.findall(req_text)))
    assert len(req_ids) >= 20, f"Too few requirement IDs detected: {len(req_ids)}"
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_tests_document_mentions_all_tiers(project_root: Path) -> None:
    text = _read(project_root / "docs" / "TESTS.md")
    for marker in ("Unit", "System", "Integration", "Application"):
        assert marker in text, f"Missing test tier marker in docs/TESTS.md: {marker}"
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_at_directories_mostly_covered_in_tests_doc(project_root: Path) -> None:
    app_dir = project_root / "tests" / "application"
    at_dirs = sorted([p.name for p in app_dir.iterdir() if p.is_dir() and p.name.startswith("AT1.")])
    tests_doc = _read(project_root / "docs" / "TESTS.md")
    covered = 0
    for at_dir in at_dirs:
        at_id = at_dir.split("_", 1)[0]
        if at_id in tests_doc:
            covered += 1
    ratio = covered / len(at_dirs) if at_dirs else 1.0
    assert ratio >= 0.80, f"AT coverage in docs/TESTS.md below 80%: {covered}/{len(at_dirs)}"
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_traceability_mentions_requirement_ids_in_tests_doc(project_root: Path) -> None:
    text = _read(project_root / "docs" / "TESTS.md")
    req_refs = sorted(set(_REQ_RE.findall(text)))
    assert len(req_refs) >= 10, f"Too few requirement references in docs/TESTS.md: {len(req_refs)}"
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_at22_placeholder_dirs_present(project_root: Path) -> None:
    assert (project_root / "tests" / "application" / "AT1.28_AudioVideoSupport").exists()
    assert (project_root / "tests" / "application" / "AT1.29_StorageApplication").exists()
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_ui_traceability_section_present(project_root: Path) -> None:
    text = _read(project_root / "docs" / "TESTS.md")
    assert "Web UI Traceability" in text
@pytest.mark.QT
@pytest.mark.mcp
@pytest.mark.req("FR-008")


def test_w28a201_non_ui_traceability_section_present(project_root: Path) -> None:
    text = _read(project_root / "docs" / "TESTS.md")
    for marker in (
        "W28A-201 Non-UI Traceability",
        "FR1.16",
        "FR1.17",
        "FR1.24",
        "FR1.25",
        "FR-P001",
        "FR-P002",
    ):
        assert marker in text, f"Missing W28A-201 traceability marker in docs/TESTS.md: {marker}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.pure, pytest.mark.fast]
