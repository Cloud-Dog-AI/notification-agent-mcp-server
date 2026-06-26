# @pytest.mark.QT
# @pytest.mark.internal
# @pytest.mark.req("NF-003")  # W28E-1807A: semantic binding (was probe; structural-conformance gate)
# PS-REQ-TEST-TRACE marker anchor for structural conformance.

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

"""QT1.1: Rules compliance checks."""

from __future__ import annotations
import pytest

from pathlib import Path
import re


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def test_required_docs_exist(project_root: Path, allowlist: dict[str, object]) -> None:
    for rel in sorted(allowlist["required_docs"]):
        assert (project_root / rel).exists(), f"Missing required document: {rel}"


def test_server_control_scripts_exist(project_root: Path) -> None:
    for rel in ("server_control.sh", "docker-build.sh", "local-docker-server.sh"):
        path = project_root / rel
        assert path.exists(), f"Missing script: {rel}"


def test_no_committed_vault_token_in_src(project_root: Path, src_dir: Path) -> None:
    token_re = re.compile(r"\bhvs\.[A-Za-z0-9_-]{20,}\b")
    hits: list[str] = []
    for path in src_dir.rglob("*.py"):
        for idx, line in enumerate(_read(path).splitlines(), 1):
            if token_re.search(line):
                hits.append(f"{path.relative_to(project_root)}:{idx}")
    assert not hits, "Vault token-like literal found in src:\n" + "\n".join(hits)


def test_runtime_env_files_present(project_root: Path, allowlist: dict[str, object]) -> None:
    for rel in sorted(allowlist["required_env_files"]):
        assert (project_root / rel).exists(), f"Missing env file: {rel}"


def test_at_suite_directories_exist(project_root: Path) -> None:
    app_dir = project_root / "tests" / "application"
    at_dirs = sorted([p.name for p in app_dir.iterdir() if p.is_dir() and p.name.startswith("AT1.")])
    assert len(at_dirs) >= 24, f"Expected >=24 AT suites, found {len(at_dirs)}"


def test_rules_reference_vault_and_server_control(project_root: Path) -> None:
    text = _read(project_root / "RULES.md")
    assert "env-vault" in text
    assert "server_control.sh" in text

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.docker, pytest.mark.fast]
