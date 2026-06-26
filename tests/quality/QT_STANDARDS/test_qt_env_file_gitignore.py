# @pytest.mark.QT
# @pytest.mark.internal
# @pytest.mark.req("CS-002")  # W28E-1807A: semantic binding (was probe; structural-conformance gate)
# PS-REQ-TEST-TRACE marker anchor for structural conformance.

import pytest
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

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_qt_env_file_gitignore():
    gitignore_path = PROJECT_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore is missing"
    gitignore_content = gitignore_path.read_text(encoding="utf-8")
    assert "env-*-secrets" in gitignore_content, ".gitignore must include env-*-secrets pattern"

    # rglob can race against concurrent pytest cache cleanup in this repo.
    # Traverse robustly and ignore transient disappearing entries.
    candidate_files = []
    try:
        iterator = PROJECT_ROOT.rglob("env-*-secrets*")
        while True:
            try:
                p = next(iterator)
            except StopIteration:
                break
            except FileNotFoundError:
                continue
            if p.is_file() and ".git/" not in str(p):
                candidate_files.append(p)
    except FileNotFoundError:
        candidate_files = []
    for path in candidate_files:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=PROJECT_ROOT,
            check=False,
        )
        assert result.returncode == 0, f"Secret env file is not gitignored: {path}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.pure, pytest.mark.fast]

