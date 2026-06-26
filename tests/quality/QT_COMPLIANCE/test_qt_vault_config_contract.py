# @pytest.mark.QT
# @pytest.mark.internal
# @pytest.mark.req("CS-002")  # W28E-1807A: semantic binding (was probe; structural-conformance gate)
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

"""QT1.5: Vault and env contract checks."""

from __future__ import annotations
import pytest

from pathlib import Path
import re


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _env_map(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in _read(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip()
    return values


def test_qt_env_file_exists(project_root: Path) -> None:
    assert (project_root / "tests" / "env-QT").exists()


def test_local_docker_env_has_vault_refs_for_secret_keys(project_root: Path) -> None:
    env_path = project_root / "tests" / "env-AT-local-docker"
    values = _env_map(env_path)
    secret_suffixes = (
        "__PASSWORD",
        "__TOKEN",
        "__SECRET",
        "__API_KEY",
        "__ACCESS_KEY",
        "__SECRET_KEY",
    )
    secret_keys = [
        key for key in values
        if key.endswith(secret_suffixes)
    ]
    bad: list[str] = []
    for key in secret_keys:
        value = values[key].strip("\"'")
        if value.startswith("$${vault.dev.") and value.endswith("}"):
            continue
        if value.startswith("${vault.dev.") and value.endswith("}"):
            continue
        if key.endswith("__API_KEY") and value.startswith("sk-"):
            continue
        bad.append(f"{key}={values[key]}")
    assert not bad, "Secret-like env entries without vault expression:\n" + "\n".join(bad)


def test_env_contract_files_exist(project_root: Path, allowlist: dict[str, object]) -> None:
    for rel in sorted(allowlist["required_env_files"]):
        assert (project_root / rel).exists(), f"Missing env file: {rel}"


def test_no_vault_token_literal_in_tests_quality(project_root: Path) -> None:
    token_re = re.compile(r"\bhvs\.[A-Za-z0-9_-]{20,}\b")
    hits: list[str] = []
    for path in (project_root / "tests" / "quality").rglob("*.py"):
        for idx, line in enumerate(_read(path).splitlines(), 1):
            if token_re.search(line):
                hits.append(f"{path.relative_to(project_root)}:{idx}")
    assert not hits, "Vault token-like literals found in QT files:\n" + "\n".join(hits)


def test_storage_s3_bucket_config_present(project_root: Path) -> None:
    env_text = _read(project_root / "tests" / "env-AT-local-server")
    assert "CLOUD_DOG__NOTIFY__FILE_CHANNEL__S3__BUCKET" in env_text


def test_vault_markers_present_in_env_files(project_root: Path) -> None:
    checked = [
        project_root / "tests" / "env-AT-local-docker",
        project_root / "tests" / "env-IT-local-docker",
        project_root / "tests" / "env-ST-local-docker",
        project_root / "tests" / "env-UT-local-docker",
    ]
    missing: list[str] = []
    for path in checked:
        text = _read(path)
        if "vault.dev." not in text:
            missing.append(path.name)
    assert not missing, "Expected vault.dev references missing in env files: " + ", ".join(missing)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.docker, pytest.mark.fast]

