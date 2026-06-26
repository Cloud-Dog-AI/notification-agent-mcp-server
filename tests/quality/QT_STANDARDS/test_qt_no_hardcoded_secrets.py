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

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
ASSIGN_RE = re.compile(
    r"(?i)\b(password|secret|token|api[_-]?key|access[_-]?key)\b\s*[:=]\s*['\"][^'\"]{4,}['\"]"
)
EXCLUDE_FILES = {
    PROJECT_ROOT / "src" / "config" / "runtime_config.py",
}


def test_qt_no_hardcoded_secrets():
    violations = []

    for py_file in SRC_ROOT.rglob("*.py"):
        if py_file in EXCLUDE_FILES:
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        for lineno, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "${vault." in line or "$${vault." in line:
                continue
            if "os.getenv(" in line or "getenv(" in line or "config.get(" in line:
                continue
            if ASSIGN_RE.search(line):
                violations.append(f"{py_file}:{lineno}:{line}")

    assert not violations, "Potential hardcoded secrets found:\n" + "\n".join(violations[:30])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.quality, pytest.mark.pure, pytest.mark.fast]

