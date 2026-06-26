#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Fast in-process integration checks for the unified HTTP app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


pytestmark = [
    pytest.mark.integration,
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]


@pytest.fixture(scope="module")
def client():
    from src.config import get_config

    get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        env_file="tests/env-IT",
        load_env_file=True,
        force_reload=True,
        unresolved_policy="empty",
    )
    from src.servers.unified_app import create_unified_app

    with TestClient(create_unified_app(env_files=["tests/env-IT"])) as test_client:
        yield test_client
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_unified_api_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "healthy"}
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.parametrize("path", ["/", "/api-docs", "/jobs", "/settings"])
def test_unified_browser_routes_prefer_spa_without_api_key(client, path):
    response = client.get(path, headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_unified_mcp_health(client, api_key):
    response = client.get("/mcp/health", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    payload = response.json()
    assert payload["server"] == "mcp"
    assert payload["endpoints"]["streamable_http"] == "/mcp"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_unified_a2a_agent_card(client):
    response = client.get("/a2a/.well-known/agent.json")
    assert response.status_code == 200
    assert response.json()["name"] == "notification-agent"
