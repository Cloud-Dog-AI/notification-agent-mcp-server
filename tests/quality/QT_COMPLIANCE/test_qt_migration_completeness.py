# @pytest.mark.QT
# @pytest.mark.internal
# @pytest.mark.req("NF-002")  # W28E-1807A: semantic binding (was probe; structural-conformance gate)
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

"""QT1.3: Migration completeness checks."""

from __future__ import annotations
import pytest

from pathlib import Path
import re


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def test_runtime_bridges_exist(project_root: Path) -> None:
    assert (project_root / "src" / "core" / "idam" / "runtime.py").exists()
    assert (project_root / "src" / "core" / "jobs" / "runtime.py").exists()


def test_database_manager_has_cloud_dog_db_contract(project_root: Path) -> None:
    text = _read(project_root / "src" / "database" / "db_manager.py")
    assert "DatabaseSettings" in text
    assert "build_sync_engine" in text


def test_no_placeholder_fill_me_tokens_in_src(src_dir: Path, project_root: Path) -> None:
    pattern = re.compile(r"\b(FILL_ME|TODO_CHANGE_ME|XXX_HARDCODED)\b")
    hits: list[str] = []
    for path in src_dir.rglob("*.py"):
        for idx, line in enumerate(_read(path).splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{path.relative_to(project_root)}:{idx}")
    assert not hits, "Placeholder migration tokens still present:\n" + "\n".join(hits)


def test_no_absolute_venv_paths_in_src(src_dir: Path, project_root: Path) -> None:
    hits: list[str] = []
    for path in src_dir.rglob("*.py"):
        for idx, line in enumerate(_read(path).splitlines(), 1):
            if "/opt/iac/Development/" in line and "notification-agent-mcp-server" in line:
                hits.append(f"{path.relative_to(project_root)}:{idx}")
    assert not hits, "Absolute workspace paths found in src:\n" + "\n".join(hits)


def test_docker_build_script_exists(project_root: Path) -> None:
    assert (project_root / "docker-build.sh").exists()


def test_server_control_script_referenced_in_rules(project_root: Path) -> None:
    text = _read(project_root / "RULES.md")
    assert "server_control.sh" in text

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.db, pytest.mark.mcp, pytest.mark.docker, pytest.mark.fast]

