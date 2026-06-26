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

"""Fixtures for QT compliance checks."""

from __future__ import annotations

from pathlib import Path
import re

import pytest


_SECRET_KEY_RE = re.compile(r"(PASSWORD|TOKEN|SECRET|API_KEY|ACCESS_KEY)")


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def src_dir(project_root: Path) -> Path:
    return project_root / "src"


@pytest.fixture(scope="session")
def qt_env_paths(request: pytest.FixtureRequest, project_root: Path) -> list[Path]:
    values = request.config.getoption("--env") or []
    resolved: list[Path] = []
    for raw in values:
        path = Path(str(raw))
        if not path.is_absolute():
            path = project_root / path
        resolved.append(path)
    return resolved


@pytest.fixture(scope="session")
def allowlist() -> dict[str, object]:
    return {
        "required_platform_packages": {
            "cloud_dog_config",
            "cloud_dog_logging",
            "cloud_dog_api_kit",
            "cloud_dog_idam",
            "cloud_dog_jobs",
            "cloud_dog_llm",
            "cloud_dog_db",
        },
        "required_docs": {
            "docs/REQUIREMENTS.md",
            "docs/TESTS.md",
            "docs/ARCHITECTURE.md",
            "RULES.md",
        },
        "required_env_files": {
            "tests/env-UT-local-docker",
            "tests/env-ST-local-docker",
            "tests/env-IT-local-docker",
            "tests/env-AT-local-docker",
        },
        "secret_key_regex": _SECRET_KEY_RE,
    }
