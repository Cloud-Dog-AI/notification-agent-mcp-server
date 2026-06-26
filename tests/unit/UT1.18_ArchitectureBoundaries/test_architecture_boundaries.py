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
UT1.18: Architecture boundary guardrails (BO1.6).

These tests enforce key code-reuse/architecture constraints so external service
access remains centralized and maintainable.
"""

from __future__ import annotations
import pytest

from pathlib import Path
import re
from typing import Iterable, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"


def _py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _line_hits(path: Path, pattern: str) -> List[Tuple[int, str]]:
    hits: List[Tuple[int, str]] = []
    rx = re.compile(pattern)
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if rx.search(line):
            hits.append((idx, line.strip()))
    return hits
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-002")


def test_ut118_llm_provider_sdk_imports_are_centralized() -> None:
    """
    Provider SDK imports must stay in llm_manager to preserve one integration surface.
    """
    allowed = {
        "src/core/llm/llm_manager.py",
    }
    patterns = [
        r"\blangchain_ollama\b",
        r"\blangchain_openai\b",
        r"\blangchain_anthropic\b",
        r"\bgoogle\.generativeai\b",
    ]

    violations: List[str] = []
    for py in _py_files(SRC_ROOT):
        rel = py.relative_to(PROJECT_ROOT).as_posix()
        if rel in allowed:
            continue
        for pattern in patterns:
            for line_no, line in _line_hits(py, pattern):
                violations.append(f"{rel}:{line_no}: {line}")

    assert not violations, (
        "LLM provider SDK imports must be centralized in src/core/llm/llm_manager.py. Violations:\n"
        + "\n".join(violations)
    )
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-002")


def test_ut118_s3_sdk_imports_are_centralized() -> None:
    """
    S3 SDK imports must stay in the S3 storage implementation.
    """
    allowed = {
        "src/core/storage/s3_storage.py",
    }
    violations: List[str] = []
    for py in _py_files(SRC_ROOT):
        rel = py.relative_to(PROJECT_ROOT).as_posix()
        if rel in allowed:
            continue
        for line_no, line in _line_hits(py, r"\bboto3\b"):
            violations.append(f"{rel}:{line_no}: {line}")

    assert not violations, (
        "boto3 imports/usages must be centralized in src/core/storage/s3_storage.py. Violations:\n"
        + "\n".join(violations)
    )
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-002")


def test_ut118_no_direct_concrete_adapter_imports_outside_registry() -> None:
    """
    Concrete adapter modules should only be imported inside the adapters package.
    """
    adapter_files = sorted((SRC_ROOT / "adapters").glob("*_adapter.py"))
    module_names = [f.stem for f in adapter_files]
    assert module_names, "No adapter modules found to validate"

    violations: List[str] = []
    for py in _py_files(SRC_ROOT):
        rel = py.relative_to(PROJECT_ROOT).as_posix()
        if rel.startswith("src/adapters/"):
            continue

        lines = py.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            for mod in module_names:
                if mod in stripped and "get_adapter_registry" not in stripped:
                    violations.append(f"{rel}:{idx}: {stripped}")

    assert not violations, (
        "Concrete adapter imports must stay inside src/adapters/ (use registry). Violations:\n"
        + "\n".join(violations)
    )

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.llm, pytest.mark.fast]

