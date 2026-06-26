#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0

"""Dependency-gate contracts for notification-agent pytest marker selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

import tests.conftest as root_conftest


@dataclass
class _FakeItem:
    nodeid: str
    markers: set[str]

    @property
    def fspath(self) -> Path:
        return Path(self.nodeid.split("::", 1)[0])

    @property
    def keywords(self) -> dict[str, bool]:
        return {marker: True for marker in self.markers}

    def get_closest_marker(self, name: str):
        return object() if name in self.markers else None


def _item(nodeid: str, *markers: str) -> _FakeItem:
    return _FakeItem(nodeid=nodeid, markers=set(markers))
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_non_llm_api_web_mcp_db_items_do_not_require_llm_dependency() -> None:
    items = [
        _item("tests/integration/IT1.1_APIServer/test_api_server.py::test_status", "integration", "db"),
        _item("tests/integration/IT1.4_WebUIEndpoints/test_webui_endpoints.py::test_settings", "integration"),
        _item("tests/integration/IT1.21_MCP_HTTP_JSONRPC/test_mcp_http_jsonrpc.py::test_tools", "integration", "mcp"),
        _item("tests/system/ST1.21_DatabaseMigration/test_database_migration_multibackend.py::test_migration", "system", "db"),
    ]

    assert root_conftest._session_requires_llm_dependency(items) is False
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_llm_markers_and_llm_test_paths_keep_llm_dependency_required() -> None:
    marked_items = [
        _item("tests/system/ST1.18_LLMFunctionality/test_llm_functionality.py::test_status", "system", "llm")
    ]
    llm_path_items = [
        _item("tests/llm_test/test_llm_direct.py::test_direct_model", "integration")
    ]

    assert root_conftest._session_requires_llm_dependency(marked_items) is True
    assert root_conftest._session_requires_llm_dependency(llm_path_items) is True
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_runtime_service_inference_keeps_worker_out_of_api_web_mcp_db_contracts() -> None:
    items = [
        _item("tests/integration/IT1.1_APIServer/test_api_server.py::test_status", "integration", "db"),
        _item("tests/integration/IT1.4_WebUIEndpoints/test_webui_endpoints.py::test_login", "integration"),
        _item("tests/integration/IT1.21_MCP_HTTP_JSONRPC/test_mcp_http_jsonrpc.py::test_tools", "integration", "mcp"),
    ]

    services = root_conftest._session_dependency_services(items)

    assert services == {"api", "web", "mcp"}
    assert "worker" not in services
    assert "a2a" not in services
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_runtime_service_inference_ignores_repository_name_mcp_token() -> None:
    item = _item(
        "tests/integration/IT1.4_WebUIEndpoints/test_webui_api_contracts.py::test_proxy_health",
        "integration",
        "api",
        "webui",
        "non_llm",
    )
    services = root_conftest._session_dependency_services([item])

    assert services == {"api", "web"}
    assert "mcp" not in services
    assert "worker" not in services
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_runtime_service_inference_adds_worker_only_for_worker_delivery_contracts() -> None:
    items = [
        _item("tests/integration/IT1.8_AsyncMessageDelivery/test_async_message_delivery.py::test_delivery", "integration")
    ]

    assert root_conftest._session_dependency_services(items) == {"api", "worker"}


pytestmark = [
    pytest.mark.unit,
    pytest.mark.fast,
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]
