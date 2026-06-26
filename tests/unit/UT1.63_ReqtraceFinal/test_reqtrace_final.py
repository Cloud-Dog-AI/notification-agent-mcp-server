from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
DOCS = ROOT / "docs"
TESTS = ROOT / "tests"

pytestmark = [
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]

CS_IDS = {f"CS-{idx:03d}" for idx in range(1, 17)}
FR_IDS = {f"FR-{idx:03d}" for idx in range(1, 27)}
NF_IDS = {f"NF-{idx:03d}" for idx in range(1, 5)}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _combined(*paths: Path) -> str:
    return "\n".join(_text(path) for path in paths)


def _req_rows() -> set[str]:
    requirements = _text(DOCS / "REQUIREMENTS.md")
    return {
        line.split("`", 2)[1]
        for line in requirements.splitlines()
        if line.startswith("| `") and line.count("`") >= 2
    }


@pytest.mark.UT
@pytest.mark.internal
@pytest.mark.req("NF-004")
def test_active_requirement_rows_are_declared_once_in_canonical_docs() -> None:
    rows = _req_rows()
    expected = CS_IDS | FR_IDS | NF_IDS

    assert expected <= rows


@pytest.mark.UT
@pytest.mark.api
@pytest.mark.mcp
@pytest.mark.a2a
@pytest.mark.webui
@pytest.mark.negative
@pytest.mark.req("CS-001")
@pytest.mark.req("CS-002")
@pytest.mark.req("CS-003")
@pytest.mark.req("CS-004")
@pytest.mark.req("CS-005")
@pytest.mark.req("CS-006")
@pytest.mark.req("CS-007")
@pytest.mark.req("CS-008")
@pytest.mark.req("CS-009")
@pytest.mark.req("CS-010")
@pytest.mark.req("CS-011")
@pytest.mark.req("CS-012")
@pytest.mark.req("CS-013")
@pytest.mark.req("CS-014")
@pytest.mark.req("CS-015")
@pytest.mark.req("CS-016")
def test_security_requirements_have_auth_rbac_validation_and_error_anchors() -> None:
    api_auth = _combined(
        SRC / "servers" / "api" / "api_server.py",
        SRC / "servers" / "api" / "admin_routes.py",
        SRC / "servers" / "api" / "channel_routes.py",
        SRC / "servers" / "api" / "message_routes.py",
        SRC / "servers" / "api" / "routes" / "callbacks.py",
    )
    web_auth = _combined(
        SRC / "servers" / "web" / "auth_routes.py",
        SRC / "servers" / "web" / "proxy_routes.py",
    )

    assert "install_auth_middleware" in api_auth
    assert "verify_api_key" in api_auth
    assert "verify_admin" in api_auth
    assert "HTTP_403_FORBIDDEN" in api_auth
    assert "HTTP_422_UNPROCESSABLE_ENTITY" in api_auth
    assert "signature" in _text(SRC / "core" / "security" / "signature.py").lower()
    assert "webapi/tests/login" in web_auth
    assert "auth/me" in web_auth
    assert "read-only" in web_auth
    assert "read-write" in web_auth


@pytest.mark.UT
@pytest.mark.api
@pytest.mark.mcp
@pytest.mark.a2a
@pytest.mark.webui
@pytest.mark.req("FR-001")
@pytest.mark.req("FR-002")
@pytest.mark.req("FR-003")
@pytest.mark.req("FR-004")
@pytest.mark.req("FR-005")
@pytest.mark.req("FR-006")
@pytest.mark.req("FR-007")
@pytest.mark.req("FR-008")
@pytest.mark.req("FR-009")
@pytest.mark.req("FR-010")
@pytest.mark.req("FR-011")
@pytest.mark.req("FR-012")
@pytest.mark.req("FR-013")
@pytest.mark.req("FR-014")
@pytest.mark.req("FR-015")
@pytest.mark.req("FR-016")
@pytest.mark.req("FR-017")
@pytest.mark.req("FR-018")
@pytest.mark.req("FR-019")
@pytest.mark.req("FR-020")
@pytest.mark.req("FR-021")
def test_functional_requirements_have_runtime_surface_anchors() -> None:
    message_routes = _text(SRC / "servers" / "api" / "message_routes.py")
    llm_formatter = _text(SRC / "core" / "formatters" / "llm_formatter.py")
    web_proxy = _text(SRC / "servers" / "web" / "proxy_routes.py")
    a2a_server = _text(SRC / "servers" / "a2a" / "a2a_server.py")
    resolver_sources = _combined(
        SRC / "core" / "resolvers" / "natural_language_parser.py",
        SRC / "core" / "resolvers" / "user_resolver.py",
        SRC / "core" / "resolvers" / "group_resolver.py",
    )

    for adapter in ("smtp_adapter.py", "sms_adapter.py", "whatsapp_adapter.py", "chat_adapter.py"):
        assert (SRC / "adapters" / adapter).is_file()

    assert "idempotency_key" in message_routes
    assert "ttl_hours" in message_routes
    assert "PromptManager" in llm_formatter
    assert "restrictions_applied" in llm_formatter
    assert "_translate" in message_routes
    assert "CircuitBreaker" in _text(SRC / "core" / "reliability" / "circuit_breaker.py")
    assert "RateLimiter" in _text(SRC / "core" / "reliability" / "rate_limiter.py")
    assert "backoff" in _text(SRC / "core" / "reliability" / "backoff_manager.py").lower()
    assert "/notify/natural" in a2a_server
    assert "UserResolver" in resolver_sources
    assert "GroupResolver" in resolver_sources
    for route in (
        "/api/proxy/channels",
        "/api/proxy/messages",
        "/api/proxy/users",
        "/api/proxy/groups",
        "/api/proxy/prompts",
        "/api/proxy/jobs",
        "/api/proxy/config",
        "/api/proxy/logs",
    ):
        assert route in web_proxy


@pytest.mark.UT
@pytest.mark.internal
@pytest.mark.media
@pytest.mark.worker
@pytest.mark.req("FR-022")
@pytest.mark.req("FR-023")
@pytest.mark.req("FR-024")
@pytest.mark.req("FR-025")
@pytest.mark.req("FR-026")
def test_cluster_requirements_have_source_and_existing_tier_test_anchors() -> None:
    source_anchors = [
        SRC / "core" / "job_manager.py",
        SRC / "core" / "storage" / "storage_manager.py",
        SRC / "core" / "formatters" / "pdf_generator.py",
        SRC / "core" / "formatters" / "message_url.py",
        SRC / "core" / "media" / "image_handler.py",
        SRC / "core" / "audit" / "enhanced_audit.py",
        SRC / "servers" / "mcp" / "mcp_server_http.py",
        SRC / "servers" / "worker" / "worker_server.py",
    ]
    for path in source_anchors:
        assert path.is_file()

    for marker in ("FR-022", "FR-023", "FR-024", "FR-025", "FR-026"):
        matches = [
            path
            for path in TESTS.rglob("test_*.py")
            if f'@pytest.mark.req("{marker}")' in _text(path)
        ]
        assert matches, marker


@pytest.mark.UT
@pytest.mark.internal
@pytest.mark.req("NF-001")
@pytest.mark.req("NF-002")
@pytest.mark.req("NF-003")
@pytest.mark.req("NF-004")
def test_nonfunctional_requirements_have_config_docs_and_quality_gates() -> None:
    quality_files = {
        "NF-001": TESTS / "quality" / "QT_STANDARDS" / "test_qt_defaults_yaml_exists.py",
        "NF-002": TESTS / "quality" / "QT_PACKAGE_COMPLIANCE" / "test_package_compliance.py",
        "NF-003": TESTS / "quality" / "QT_COMPLIANCE" / "test_qt3_documentation_suite.py",
        "NF-004": TESTS / "quality" / "QT_MARKER_GATES" / "test_marker_taxonomy.py",
    }

    assert (ROOT / "defaults.yaml").is_file()
    assert (ROOT / "pyproject.toml").is_file()
    for doc_name in ("REQUIREMENTS.md", "REQ-COVERAGE.md", "TESTS.md", "TEST-STATUS.md"):
        assert (DOCS / doc_name).is_file()
    for marker, path in quality_files.items():
        assert path.is_file()
        assert marker in _text(path)
