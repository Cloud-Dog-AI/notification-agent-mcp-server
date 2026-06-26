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

"""QT1.2: Platform package adoption checks."""

from __future__ import annotations
import pytest

from pathlib import Path
import re


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _src_contains_import(root: Path, package: str) -> bool:
    pattern = re.compile(rf"^\s*(?:from|import)\s+{re.escape(package)}(?:\.|\s|$)", re.M)
    for path in (root / "src").rglob("*.py"):
        if pattern.search(_read(path)):
            return True
    return False


def test_requirements_declares_platform_packages(project_root: Path, allowlist: dict[str, object]) -> None:
    text = _read(project_root / "requirements.txt")
    for package in sorted(allowlist["required_platform_packages"]):
        assert package in text, f"Missing dependency in requirements.txt: {package}"


def test_pyproject_declares_platform_packages(project_root: Path, allowlist: dict[str, object]) -> None:
    text = _read(project_root / "pyproject.toml")
    for package in sorted(allowlist["required_platform_packages"]):
        assert package in text, f"Missing dependency in pyproject.toml: {package}"


def test_src_imports_required_platform_packages(project_root: Path, allowlist: dict[str, object]) -> None:
    for package in sorted(allowlist["required_platform_packages"]):
        assert _src_contains_import(project_root, package), f"Missing src import usage: {package}"


def test_database_manager_uses_cloud_dog_db(project_root: Path) -> None:
    text = _read(project_root / "src" / "database" / "db_manager.py")
    assert "from cloud_dog_db import DatabaseSettings, build_sync_engine" in text


def test_runtime_config_uses_cloud_dog_config(project_root: Path) -> None:
    text = _read(project_root / "src" / "config" / "runtime_config.py")
    assert "from cloud_dog_config import load_config" in text


def test_api_server_uses_cloud_dog_api_kit(project_root: Path) -> None:
    text = _read(project_root / "src" / "servers" / "api" / "api_server.py")
    assert "cloud_dog_api_kit" in text


def test_web_server_uses_cloud_dog_api_kit(project_root: Path) -> None:
    text = _read(project_root / "src" / "servers" / "web" / "web_server.py")
    assert "cloud_dog_api_kit" in text


def test_a2a_server_uses_cloud_dog_api_kit(project_root: Path) -> None:
    text = _read(project_root / "src" / "servers" / "a2a" / "a2a_server.py")
    assert "cloud_dog_api_kit" in text


def test_no_structlog_bootstrap_in_src(project_root: Path, src_dir: Path) -> None:
    violations: list[str] = []
    for path in src_dir.rglob("*.py"):
        for idx, line in enumerate(_read(path).splitlines(), 1):
            if "structlog" in line:
                violations.append(f"{path.relative_to(project_root)}:{idx}")
    assert not violations, "Found structlog usage (project should use cloud_dog_logging):\n" + "\n".join(violations)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.db, pytest.mark.fast]
