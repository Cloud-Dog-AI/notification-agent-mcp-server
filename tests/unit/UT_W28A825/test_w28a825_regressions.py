from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]

pytestmark = [
    pytest.mark.unit,
    pytest.mark.pure,
    pytest.mark.non_llm,
    pytest.mark.no_runtime_dependency,
]
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_web_session_middleware_wraps_spa_middleware():
    source = (PROJECT_ROOT / "src/servers/web/web_server.py").read_text()

    spa_index = source.index("async def spa_asset_middleware")
    session_index = source.rindex("app.add_middleware(\n    SessionMiddleware")

    assert session_index > spa_index
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_web_api_docs_route_is_not_caught_by_api_passthrough_prefix():
    source = (PROJECT_ROOT / "src/servers/web/web_server.py").read_text()

    assert "path.startswith(_ui_passthrough_prefixes)" not in source
    assert 'path == prefix or path.startswith(f"{prefix}/")' in source
    assert '"/openapi.json"' in source
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_server_control_all_mode_includes_web_and_a2a():
    source = (PROJECT_ROOT / "server_control.sh").read_text()

    assert "ALL_SERVERS=(api worker mcp web a2a)" in source
    assert "STOP_SERVERS=(a2a web mcp worker api)" in source
    assert "SERVERS[web]=" in source
    assert "SERVERS[a2a]=" in source
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_channel_delete_uses_structured_conflict_without_raw_db_detail():
    route_source = (PROJECT_ROOT / "src/servers/api/channel_routes.py").read_text()
    repo_source = (PROJECT_ROOT / "src/database/repositories.py").read_text()
    proxy_source = (PROJECT_ROOT / "src/servers/web/proxy_routes.py").read_text()

    assert "def count_deliveries" in repo_source
    assert "channel_repo.count_deliveries(channel_id)" in route_source
    assert '"code": "channel_in_use"' in route_source
    assert '"code": "channel_delete_failed"' in route_source
    assert "detail=f\"Failed to delete channel" not in route_source
    assert "detail=f'Failed to delete channel" not in route_source
    delete_proxy = proxy_source[
        proxy_source.index("async def proxy_delete_channel"):
        proxy_source.index("@router.post(\"/api/proxy/channels/{channel_id}/test\")")
    ]
    assert "except HTTPException:\n        raise" in delete_proxy
