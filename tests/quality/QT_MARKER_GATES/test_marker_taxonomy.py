# @pytest.mark.QT
# @pytest.mark.internal
# @pytest.mark.req("NF-004")  # W28E-1807A: semantic binding (was probe; structural-conformance gate)
# PS-REQ-TEST-TRACE marker anchor for structural conformance.

import configparser
from pathlib import Path

import pytest

from tests.conftest import _taxonomy_markers_for_nodeid


pytestmark = [
    pytest.mark.quality,
    pytest.mark.non_llm,
    pytest.mark.fast,
    pytest.mark.no_runtime_dependency,
]


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTEST_INI = REPO_ROOT / "pytest.ini"
TESTS_DOC = REPO_ROOT / "docs" / "TESTS.md"
REQUIRED_MARKERS = {
    "non_llm",
    "api",
    "webui",
    "mcp",
    "db",
    "media",
    "worker",
    "forensic",
    "live_provider",
    "live_delivery",
    "llm",
    "llm_real",
    "generated_answer",
    "no_llm_dependency",
    "dependency_services",
    "fast",
    "slow",
    "heavy",
    "quality",
    "unit",
    "system",
    "integration",
    "application",
}
FAST_NON_LLM_SELECTOR = (
    "non_llm and fast and not llm and not llm_real and not generated_answer "
    "and not live_provider and not live_delivery"
)


def _declared_pytest_markers() -> set[str]:
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI)
    marker_lines = parser.get("pytest", "markers").splitlines()
    return {line.strip().split(":", 1)[0].split("(", 1)[0] for line in marker_lines if line.strip()}


def test_pytest_ini_declares_notification_gate_taxonomy() -> None:
    missing = REQUIRED_MARKERS - _declared_pytest_markers()
    assert not missing, f"pytest.ini is missing marker declarations: {sorted(missing)}"


def test_non_llm_gate_commands_are_documented_with_live_exclusions() -> None:
    tests_doc = TESTS_DOC.read_text(encoding="utf-8")
    assert FAST_NON_LLM_SELECTOR in tests_doc
    assert "--collect-only" in tests_doc
    assert "tests/env-QT" in tests_doc
    assert "tests/env-UT" in tests_doc


def test_collection_taxonomy_excludes_llm_and_live_provider_cases() -> None:
    llm_markers = _taxonomy_markers_for_nodeid(
        "tests/unit/UT1.6_LLMManager/test_llm_manager.py::test_connect"
    )
    live_markers = _taxonomy_markers_for_nodeid(
        "tests/application/AT1.5_FrenchSummary/test_at1_5_smtp_variants.py::test_smtp"
    )
    api_markers = _taxonomy_markers_for_nodeid(
        "tests/integration/IT1.4_WebUIEndpoints/test_webui_endpoints.py::test_health"
    )
    generated_markers = _taxonomy_markers_for_nodeid(
        "tests/application/AT1.4_Comprehensive/test_at1_4f_summary_full.py::"
        "test_at1_4f_summary_full[en_to_fr_5000_summary]"
    )
    slack_markers = _taxonomy_markers_for_nodeid(
        "tests/application/AT1.27_SlackSummaryLink/test_slack_summary_link.py::"
        "test_slack_summary_link"
    )

    assert "llm" in llm_markers
    assert "non_llm" not in llm_markers
    assert {"live_provider", "live_delivery"}.issubset(live_markers)
    assert "non_llm" not in live_markers
    assert {"api", "webui", "non_llm"}.issubset(api_markers)
    assert {"llm", "generated_answer"}.issubset(generated_markers)
    assert "non_llm" not in generated_markers
    assert {"live_provider", "live_delivery", "llm", "generated_answer"}.issubset(slack_markers)
    assert "non_llm" not in slack_markers


def test_worker_forensic_paths_are_separate_from_fast_contract_collections() -> None:
    worker_markers = _taxonomy_markers_for_nodeid(
        "tests/integration/IT1.25_AsyncMessageSubmission/test_async_message_submission.py::"
        "test_message_submission_rejects_when_delivery_queue_is_full",
        {"integration", "worker", "forensic", "no_llm_dependency"},
    )
    restart_markers = _taxonomy_markers_for_nodeid(
        "tests/integration/IT1.8_AsyncMessageDelivery/test_async_message_delivery.py::"
        "test_delivery_survives_server_restart",
        {"integration", "worker", "forensic", "llm"},
    )
    readiness_markers = _taxonomy_markers_for_nodeid(
        "tests/unit/UT1.20_RuntimeArchitectureContracts/test_delivery_worker_startup_backlog.py::"
        "test_capture_startup_backlog_max_id_uses_current_delivery_high_watermark",
        {"unit", "worker", "forensic", "fast", "no_runtime_dependency", "no_llm_dependency"},
    )

    assert {"worker", "forensic", "non_llm"}.issubset(worker_markers)
    assert {"worker", "forensic", "llm"}.issubset(restart_markers)
    assert "non_llm" not in restart_markers
    assert {"worker", "forensic", "non_llm", "fast"}.issubset(readiness_markers)
    assert "api" not in worker_markers
    assert "webui" not in worker_markers
