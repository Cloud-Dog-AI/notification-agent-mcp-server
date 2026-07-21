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
Description: Project-local Python runtime contract preflight for notification-agent-mcp-server.

The remediated runtime for this service is Python 3.13 (W28R-3017 supply-chain
remediation — the 3.12->3.13 base bump clears the fixable CPython High/Critical
CVEs). Per the W28R-3008..3021 playbook addendum "Project Runtime Contract", the
project-local developer/test contract must move with the container runtime: a bare
`Dockerfile FROM ...:3.13-slim` is not enough. This module fails fast (at package
import, on every entrypoint) if the interpreter is older than 3.13, so a fresh
developer, test run, or container can never silently regress to a vulnerable runtime.

Related Requirements: NF-005
Related Tasks: T-W28R-3017
Related Architecture: SP1.1
Related Tests: UT (test_ut_runtime_contract.py)

Recent Changes (max 10):
- W28R-3017: added project-local Python 3.13 runtime contract preflight.

**************************************************
"""

from __future__ import annotations

import sys

# Minimum supported interpreter for this service (project-local runtime contract).
MINIMUM_PYTHON: tuple[int, int] = (3, 13)


class RuntimeContractError(RuntimeError):
    """Raised when the active interpreter violates the project runtime contract."""


def enforce_runtime(minimum: tuple[int, int] = MINIMUM_PYTHON) -> None:
    """Fail fast unless the active interpreter satisfies the project runtime contract.

    Args:
        minimum: (major, minor) minimum supported Python version. Defaults to 3.13.

    Raises:
        RuntimeContractError: if ``sys.version_info`` is older than ``minimum``.
    """
    if sys.version_info[:2] < minimum:
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        required = f"{minimum[0]}.{minimum[1]}"
        raise RuntimeContractError(
            f"notification-agent-mcp-server requires Python >= {required} "
            f"(project runtime contract, W28R-3017); active interpreter is {current}. "
            f"Create and use a Python {required} virtual environment "
            f"(python3.13 -m venv .venv)."
        )


if __name__ == "__main__":  # pragma: no cover - CLI preflight helper
    try:
        enforce_runtime()
    except RuntimeContractError as exc:
        print(f"RUNTIME_CONTRACT_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(
        "RUNTIME_CONTRACT_OK: python "
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
