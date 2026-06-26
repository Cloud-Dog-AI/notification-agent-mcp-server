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
Pytest configuration and fixtures for Notification Agent MCP Server tests

Handles:
- Config loading from --env flag (os.environ -> env file -> config.yaml -> defaults.yaml)
- Graceful failure for missing settings
- Test configuration setup
"""

import pytest
import os
import sys
import httpx
import asyncio
import time
import tempfile
import subprocess
import re
import shlex
import socket
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import RuntimeConfig, get_config
from src.database.db_manager import DatabaseManager
from src.core.job_manager import JobManager
from tests.utils.api_tracking import ApiCleanupRegistry

_RUNTIME_MODES = {"local-server", "local-docker", "remote-runtime"}
_VAULT_REF_PATTERN = re.compile(r"\$\{(vault\.[^}]+)\}")
_TEST_TIER_MARKERS = {
    "QT": "quality",
    "UT": "unit",
    "ST": "system",
    "IT": "integration",
    "AT": "application",
}
_TEST_TIER_PATHS = {
    "quality": "quality",
    "unit": "unit",
    "system": "system",
    "integration": "integration",
    "application": "application",
}
_LLM_DEPENDENCY_MARKERS = {"llm", "llm_real", "generated_answer"}
_LIVE_PROVIDER_MARKERS = {"live_provider", "live_delivery"}
_NON_LLM_MARKER = "non_llm"
_NO_LLM_DEPENDENCY_MARKER = "no_llm_dependency"
_NO_RUNTIME_DEPENDENCY_MARKER = "no_runtime_dependency"
_MARKER_TAXONOMY_RULES = (
    (("api", "api_server", "apiserver", "endpoint", "endpoints"), ("api",)),
    (("webui", "web_ui", "playwright", "browser"), ("webui",)),
    (("mcp",), ("mcp",)),
    (("database", "storage", "db_", "multi_dialect"), ("db",)),
    (("media", "multimedia", "pdf", "image", "audio", "video", "html"), ("media",)),
    (
        ("worker", "job", "queue", "asyncmessage", "async_message", "delivery", "deliveries"),
        ("worker",),
    ),
    (("forensic", "audit", "logging", "traceability"), ("forensic",)),
    (
        (
            "slackrealintegration",
            "slack_real_integration",
            "slackwebhook",
            "slack_webhook",
            "slacksummarylink",
            "slack_summary_link",
            "slack_multilanguage",
            "realchanneladapters",
            "real_channel_adapters",
            "real_adapters",
            "transparentbordes",
            "smtp_variants",
            "emailvalidation",
            "email_validation",
            "email_comprehensive",
            "email_channel_crud",
            "email_french_translation",
            "email_attachment",
            "emailattachments",
            "french_summary_to_gary",
        ),
        ("live_provider", "live_delivery"),
    ),
    (
        (
            "llm_test",
            "llmrealintegration",
            "llmmanager",
            "llm_manager",
            "llmformatter",
            "llm_formatter",
            "llmfunctionality",
            "llm_functionality",
            "llmqueuestatus",
            "llm_queue_status",
            "natural_language",
            "naturallanguage",
            "translation",
            "frenchsummary",
            "summary",
            "summarisation",
            "summarization",
            "generated_answer",
            "at1_4_comprehensive",
            "test_at1_4",
            "pdf_language_summary",
            "language_summary",
            "promptmanagement",
            "prompt_management",
            "configureprompts",
            "personalised",
            "personalized",
            "group_personalization",
        ),
        ("llm", "generated_answer"),
    ),
)
_SERVICE_INFERENCE_TOKENS = {
    "web": ("webui", "web_ui", "playwright", "browser"),
    "mcp": ("mcp",),
    "a2a": ("a2a",),
    "worker": (
        "worker",
        "delivery",
        "deliveries",
        "async_message",
        "confirmations",
        "broadcast",
        "personalised",
        "personalized",
    ),
}


def _taxonomy_markers_for_nodeid(
    nodeid: str, initial_markers: tuple[str, ...] | set[str] | None = None
) -> set[str]:
    """Resolve gate taxonomy markers from existing markers and stable test path tokens."""
    marker_names = set(initial_markers or ())
    normalized_nodeid = nodeid.lower().replace("-", "_")
    for tokens, markers in _MARKER_TAXONOMY_RULES:
        if any(token in normalized_nodeid for token in tokens):
            marker_names.update(markers)

    if not marker_names.intersection(_LLM_DEPENDENCY_MARKERS | _LIVE_PROVIDER_MARKERS):
        marker_names.add(_NON_LLM_MARKER)
    return marker_names


def _normalise_gate_markers(item: pytest.Item) -> None:
    existing_markers = {mark.name for mark in item.iter_markers()}
    marker_names = _taxonomy_markers_for_nodeid(item.nodeid, existing_markers)
    for marker_name in sorted(marker_names - existing_markers):
        item.add_marker(getattr(pytest.mark, marker_name))


def pytest_itemcollected(item: pytest.Item) -> None:
    _normalise_gate_markers(item)


@lru_cache(maxsize=1)
def _vault_config_blob() -> dict[str, Any] | None:
    addr = os.environ.get("VAULT_ADDR", "").strip()
    token = os.environ.get("VAULT_TOKEN", "").strip()
    if not addr or not token:
        return None

    mount = os.environ.get("VAULT_MOUNT_POINT", "").strip().strip("/")
    config_path = os.environ.get("VAULT_CONFIG_PATH", "").strip().strip("/")
    try:
        secret_path = "/".join([part for part in (mount, "data", config_path) if part])
        if not secret_path:
            return None
        response = httpx.get(
            f"{addr.rstrip('/')}/v1/{secret_path}",
            headers={"X-Vault-Token": token},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", {}).get("data", {})
        if isinstance(data, dict) and "json" in data:
            json_val = data["json"]
            if isinstance(json_val, dict):
                return json_val
            if isinstance(json_val, str):
                import json as _json
                try:
                    parsed = _json.loads(json_val)
                    if isinstance(parsed, dict):
                        return parsed
                except (ValueError, TypeError):
                    pass
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _resolve_vault_path(identifier: str) -> str | None:
    path = identifier[len("vault.") :] if identifier.startswith("vault.") else identifier
    if not path:
        return None
    current: Any = _vault_config_blob()
    if not isinstance(current, dict):
        return None
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, (str, int, float, bool)):
        resolved = str(current).strip()
        return resolved or None
    return None


def _resolve_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return value

    def _replace(match: re.Match[str]) -> str:
        resolved = _resolve_vault_path(match.group(1))
        return resolved if resolved is not None else match.group(0)

    return _VAULT_REF_PATTERN.sub(_replace, value)


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[key] = _resolve_env_value(value)
    return values


def _raw_env_args(option_value: object) -> list[str]:
    if isinstance(option_value, str):
        values = [option_value]
    elif isinstance(option_value, list):
        values = [str(v) for v in option_value]
    else:
        values = []
    return [v.strip() for v in values if str(v).strip()]


def _resolve_env_paths(option_value: object) -> list[Path]:
    resolved: list[Path] = []
    for raw in _raw_env_args(option_value):
        path = Path(raw)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(
                f"Environment file not found: {raw}\n"
                "Specify with: pytest --env <env-file>\n"
                "Use: pytest --env <env-file>"
            )
        resolved.append(path)
    return resolved


def _merge_env_values(env_paths: list[Path]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for env_path in env_paths:
        merged.update(_parse_env_file(env_path))
    return merged


def _overlay_env_values(env_paths: list[Path]) -> Dict[str, str]:
    """Return only overlay env-file values, preserving base env-file loading via --env."""
    if len(env_paths) <= 1:
        return {}
    return _merge_env_values(env_paths[1:])


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_runtime_contract(env_values: Dict[str, str]) -> Tuple[str, bool, str, str]:
    raw_mode = str(env_values.get("TEST_RUNTIME_MODE") or "local-server").strip().lower()
    if raw_mode not in _RUNTIME_MODES:
        pytest.exit(
            f"CRITICAL ERROR: unsupported TEST_RUNTIME_MODE '{raw_mode}', expected one of {sorted(_RUNTIME_MODES)}",
            returncode=2,
        )

    explicit_external = env_values.get("TEST_USE_EXTERNAL_RUNTIME")
    if explicit_external is None or str(explicit_external).strip() == "":
        use_external = raw_mode in {"local-docker", "remote-runtime"}
    else:
        use_external = _truthy(explicit_external)

    test_api_base_url = str(env_values.get("TEST_API_BASE_URL") or "").strip()
    test_mcp_base_url = str(env_values.get("TEST_MCP_BASE_URL") or "").strip()
    return raw_mode, use_external, test_api_base_url, test_mcp_base_url


def _health_payload(base_url: str, timeout: float = 5.0) -> dict | None:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url.rstrip('/')}/health")
        if response.status_code != 200:
            return None
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _api_key_is_accepted(base_url: str, api_key: str, timeout: float = 5.0) -> bool:
    if not base_url or not api_key:
        return False
    paths = ("/status", "/api/v1/status")
    try:
        with httpx.Client(timeout=timeout) as client:
            for path in paths:
                response = client.get(
                    f"{base_url.rstrip('/')}{path}",
                    headers={"X-API-Key": str(api_key)},
                )
                if response.status_code == 200:
                    return True
        return False
    except Exception:
        return False


def _tcp_port_is_open(base_url: str, timeout: float = 2.0) -> bool:
    try:
        parsed = urlparse(str(base_url))
        host = parsed.hostname
        port = parsed.port
        if not host or port is None:
            return False
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def _cancel_stale_queued_messages(
    api_base_url: str,
    api_key: str,
    keep_message_id: int | None = None,
) -> int:
    """Cancel queued messages left behind by prior runs so live-runtime tests stay deterministic."""
    if not api_base_url or not api_key:
        return 0

    cancelled = 0
    headers = {"X-API-Key": str(api_key)}
    base = str(api_base_url).rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            list_resp = client.get(
                f"{base}/messages",
                headers=headers,
                params={"status": "queued", "limit": 200},
            )
            if list_resp.status_code != 200:
                return 0
            payload = list_resp.json()
            items = payload if isinstance(payload, list) else payload.get("items", [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                message_id = item.get("id")
                if message_id is None:
                    continue
                try:
                    numeric_id = int(message_id)
                except Exception:
                    continue
                if keep_message_id is not None and numeric_id == int(keep_message_id):
                    continue
                try:
                    cancel_resp = client.post(
                        f"{base}/messages/{numeric_id}/cancel",
                        headers=headers,
                    )
                    if cancel_resp.status_code in {200, 202}:
                        cancelled += 1
                except Exception:
                    continue
    except Exception:
        return cancelled

    return cancelled


def _run_server_control(
    env_file: str,
    action: str,
    service: str,
    env_overrides: Dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    # Resolve ${vault.*} references in the notify env before handing them to the
    # restarted runtime. server_control reloads the --env file, but the local
    # runtime has no approle creds and cannot resolve vault refs, so a stripped
    # reload degrades the stack (auth.jwt_secret / api_server.api_key empty ->
    # 401 on the loopback delivery callback, ST1.14 perf delivery never
    # completes). The test session already has vault read access, so resolve the
    # literals here and pass them through.
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CLOUD_DOG__NOTIFY__")
    }
    for key, value in os.environ.items():
        if key.startswith("CLOUD_DOG__NOTIFY__"):
            child_env[key] = _resolve_env_value(value)
    if env_overrides:
        child_env.update({key: str(value) for key, value in env_overrides.items()})
    return subprocess.run(
        ["./server_control.sh", "--env", env_file, action, service],
        cwd=str(project_root),
        env=child_env,
        text=True,
        capture_output=True,
        check=False,
    )


def _restart_local_service(env_file: str, service: str, env_overrides: Dict[str, str] | None = None):
    target = service
    commands = [
        ["./server_control.sh", "--env", env_file, "stop", target],
        ["./server_control.sh", "--env", env_file, "start", target],
    ]
    stop_result = _run_server_control(env_file, "stop", target, env_overrides)
    result = _run_server_control(env_file, "start", target, env_overrides)
    if result.returncode != 0:
        pytest.fail(
            "Failed to manage local runtime service for dependency checks.\n"
            f"Commands: {' && '.join(' '.join(cmd) for cmd in commands)}\n"
            f"stop stdout:\n{stop_result.stdout}\n"
            f"stop stderr:\n{stop_result.stderr}\n"
            f"start stdout:\n{result.stdout}\n"
            f"start stderr:\n{result.stderr}"
        )


def _wait_for_health(base_url: str, timeout_seconds: float = 60.0) -> dict | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = _health_payload(base_url, timeout=5.0)
        if payload is not None:
            return payload
        time.sleep(1.0)
    return None


def _ensure_api_ready_for_test(
    api_base_url: str,
    api_key: str,
    *,
    timeout_seconds: float = 60.0,
    context_label: str = "test",
) -> tuple[dict, int]:
    """Lightweight per-test isolation for API-backed suites.

    The heavy AT suites historically restarted the API between tests to clear
    queued state. For notification-agent this is far more expensive than the
    state boundary actually required. The useful guard here is:
    1. the API must be healthy
    2. leftover queued messages from a prior case must be cancelled
    """
    health = _wait_for_health(api_base_url, timeout_seconds=timeout_seconds)
    if health is None:
        pytest.fail(f"❌ API not ready before {context_label}")
    cancelled = _cancel_stale_queued_messages(api_base_url, api_key)
    return health, cancelled


def _warm_llm_runtime(llm_manager: Any, test_config: Any) -> None:
    """Prime the configured LLM so the first real test call does not absorb model load time."""
    prompt = str(
        test_config.get("test.llm_warmup_prompt")
        or "Reply with OK only."
    ).strip()
    warmup_timeout = float(
        test_config.get("llm.model_load_timeout")
        or test_config.get("llm.query_timeout")
        or 180
    )
    response = llm_manager.invoke(
        prompt,
        timeout=warmup_timeout,
        params={"num_predict": 16},
    )
    if not str(response or "").strip():
        raise RuntimeError("LLM warm-up returned empty response")


def pytest_addoption(parser):
    """Add custom command line options for pytest"""
    parser.addoption(
        "--env",
        action="append",
        default=None,
        help="Environment file path(s). Pass multiple --env entries to apply base + overlays."
    )


def pytest_configure(config):
    """
    CRITICAL: Enforce --env file requirement for ALL tests.
    Tests MUST use config hierarchy (os.environ -> env file -> config.yaml -> defaults.yaml)
    NO hardcoded passwords, API keys, hostnames, or URLs allowed in tests.
    """
    env_args = _raw_env_args(config.getoption("--env"))
    if not env_args:
        pytest.exit(
            "\n"
            "❌ CRITICAL: --env file parameter is REQUIRED for all tests\n"
            "\n"
            "Usage:\n"
            "  pytest --env private/env-test tests/...\n"
            "\n"
            "All test configuration MUST come from:\n"
            "  1. OS Environment Variables (CLOUD_DOG__NOTIFY__*)\n"
            "  2. env file (from --env flag)\n"
            "  3. config.yaml\n"
            "  4. defaults.yaml\n"
            "\n"
            "NO hardcoded values (passwords, API keys, hosts) allowed in tests.\n",
            returncode=1
        )
    try:
        _resolve_env_paths(env_args)
    except FileNotFoundError as exc:
        pytest.exit(str(exc), returncode=1)
    config.addinivalue_line(
        "markers",
        "dependency_services(*names): limit local-server dependency restarts to the named services",
    )
    config.addinivalue_line(
        "markers",
        "no_llm_dependency: test selection does not require LLM availability or warm-up",
    )
    for marker_decl in (
        # PS-REQ-TEST-TRACE canonical tier markers (UPPER-CASE)
        "QT: PS-REQ-TEST-TRACE quality tier",
        "UT: PS-REQ-TEST-TRACE unit tier",
        "ST: PS-REQ-TEST-TRACE system tier",
        "IT: PS-REQ-TEST-TRACE integration tier",
        "AT: PS-REQ-TEST-TRACE application tier",
        # PS-REQ-TEST-TRACE canonical surface + meta markers
        "req(*ids): PS-REQ-TEST-TRACE semantic requirement binding",
        "mcp: MCP surface and external MCP server coverage",
        "a2a: A2A surface",
        "cli: CLI/process surface",
        "internal: internal service surface",
        "probe: PS-REQ-TEST-TRACE orphan probe (must be listed in probe-retention-register.tsv)",
        "negative: PS-REQ-TEST-TRACE negative/denial test (CS-NNN binding)",
        "security: security/auth boundary tests",
        # Existing domain markers (kept for backward compat)
        "non_llm: safe for non-LLM gates; must not require LLM/provider warm-up",
        "live_provider: requires a real external delivery/provider endpoint",
        "live_delivery: sends or validates delivery through a live external provider",
        "generated_answer: asserts model-generated translation, summarisation, personalised, or prompt-driven content",
        "api: requires notification API server surface",
        "webui: requires notification WebUI/browser surface",
        "media: media, attachment, PDF, image, audio, video, or HTML rendering coverage",
        "worker: queue, async job, delivery worker, or background processing coverage",
        "forensic: audit, logging, traceability, or forensic evidence coverage",
        "llm_real: requires a real LLM integration/provider endpoint",
    ):
        config.addinivalue_line("markers", marker_decl)


def _item_tier_marker(item: pytest.Item) -> str | None:
    """Resolve the tier marker for a collected test item."""
    for marker in _TEST_TIER_MARKERS.values():
        if item.get_closest_marker(marker):
            return marker

    parts = Path(str(item.fspath)).parts
    if "tests" not in parts:
        return None
    tests_idx = parts.index("tests")
    if len(parts) <= tests_idx + 1:
        return None

    folder = parts[tests_idx + 1]
    for marker, path_name in _TEST_TIER_PATHS.items():
        if folder == path_name:
            return marker
    return None


def _item_has_marker(item: pytest.Item, marker_names: set[str] | tuple[str, ...]) -> bool:
    for marker_name in marker_names:
        getter = getattr(item, "get_closest_marker", None)
        if callable(getter) and getter(marker_name):
            return True
        if marker_name in getattr(item, "keywords", {}):
            return True
    return False


def _item_identity(item: pytest.Item) -> str:
    nodeid = str(getattr(item, "nodeid", "") or "")
    return nodeid.replace("\\", "/").lower()


def _all_items_marked(items: list[pytest.Item], marker_name: str) -> bool:
    return bool(items) and all(_item_has_marker(item, (marker_name,)) for item in items)


def _session_requires_llm_dependency(items: list[pytest.Item]) -> bool:
    """Return True only when the collected selection declares an LLM capability."""
    if not items:
        return True
    for item in items:
        identity = _item_identity(item)
        if _item_has_marker(item, _LLM_DEPENDENCY_MARKERS):
            return True
        # Match the llm_test path whether the identity is a bare nodeid
        # ("tests/llm_test/..."), an absolute path ("/.../tests/llm_test/...")
        # or a space-prefixed form — _item_identity returns the lower-cased
        # nodeid, which has no leading slash/space.
        if "tests/llm_test/" in identity:
            return True
    return False


def _session_dependency_services(items: list[pytest.Item]) -> set[str]:
    """Infer runtime services from collected tests without starting unrelated services."""
    if not items:
        return {"api", "web", "mcp", "a2a", "worker"}

    services = {"api"}
    for item in items:
        identity = _item_identity(item)
        if _item_has_marker(item, ("mcp",)):
            services.add("mcp")
        for service, tokens in _SERVICE_INFERENCE_TOKENS.items():
            if any(token in identity for token in tokens):
                services.add(service)
    return services


# --- PS-REQ-TEST-TRACE marker enforcement (W28E-1807A) ---------------------------
# PS-REQ-TEST-TRACE marker enforcement: fail the collection session if any collected
# test file lacks the mandatory markers: a tier (QT/UT/ST/IT/AT), a surface
# (api/mcp/a2a/webui/cli/internal), and a req()/probe binding. Markers may be real
# decorators or the repo file-header comment-anchor convention. Probes are exempt
# from req() per PS-REQ-TEST-TRACE (probe = structural conformance).
_PS_TIER_TOKENS = ("QT", "UT", "ST", "IT", "AT")
_PS_SURFACE_TOKENS = ("api", "mcp", "a2a", "webui", "cli", "internal")


def _enforce_ps_req_test_trace_markers(items):
    seen = set()
    missing = []
    for item in items:
        fspath = str(getattr(item, "fspath", "") or "")
        if not fspath or fspath in seen:
            continue
        seen.add(fspath)
        try:
            text = Path(fspath).read_text(errors="replace")
        except OSError:
            continue
        has_tier = any(("@pytest.mark." + m) in text for m in _PS_TIER_TOKENS)
        has_surface = any(("@pytest.mark." + m) in text for m in _PS_SURFACE_TOKENS)
        has_req_or_probe = (("@pytest.mark." + "req(") in text) or (("@pytest.mark." + "probe") in text)
        if not (has_tier and has_surface and has_req_or_probe):
            missing.append(fspath)
    if missing:
        pytest.exit(
            "PS-REQ-TEST-TRACE marker enforcement: test file(s) lack tier+surface+req()/probe markers: "
            + "; ".join(sorted(missing)),
            returncode=3,
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Restrict broad test collection to the tier declared by the env file."""
    _enforce_ps_req_test_trace_markers(items)
    for item in items:
        _normalise_gate_markers(item)

    env_args = _raw_env_args(config.getoption("--env"))
    if not env_args:
        return

    try:
        env_paths = _resolve_env_paths(env_args)
    except FileNotFoundError:
        return

    env_values = _merge_env_values(env_paths)
    env_tier = str(env_values.get("TEST_ENV_TIER") or "").strip().upper()
    wanted_marker = _TEST_TIER_MARKERS.get(env_tier)
    if not wanted_marker:
        return

    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        item_tier = _item_tier_marker(item)
        if item_tier == wanted_marker:
            selected.append(item)
        else:
            deselected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected

    runtime_mode = str(env_values.get("TEST_RUNTIME_MODE") or "").strip()
    use_external_runtime = _truthy(str(env_values.get("TEST_USE_EXTERNAL_RUNTIME") or ""))
    if runtime_mode == "local-server" and not use_external_runtime:
        return

    # Skip webui-marked tests unless web server is running (W28A-925b)
    web_base_url = str(
        env_values.get("CLOUD_DOG__NOTIFY__WEB_SERVER__BASE_URL")
        or env_values.get("CLOUD_DOG__WEB_SERVER__BASE_URL")
        or "http://127.0.0.1:8020"
    ).rstrip("/")
    try:
        r = httpx.get(f"{web_base_url}/health", timeout=5)
        web_running = r.status_code == 200
    except Exception:
        web_running = False

    if not web_running:
        skip_webui = pytest.mark.skip(reason=f"WebUI tests need web server at {web_base_url}")
        for item in items:
            if "webui" in item.keywords:
                item.add_marker(skip_webui)


def _dependency_service_urls(test_config, *, include_web_mcp_a2a: bool, request=None):
    selected = None
    configured = str(test_config.get("test.dependency_services") or "").strip()
    if configured:
        selected = {part.strip() for part in configured.split(",") if part.strip()}
    if request is not None:
        marker = request.node.get_closest_marker("dependency_services")
        if marker and selected is None:
            selected = {str(arg).strip() for arg in marker.args if str(arg).strip()}

    service_urls = [("api", str(test_config.get("api_server.base_url") or "").strip())]
    if include_web_mcp_a2a:
        inferred = {"api"}
        if selected is None and request is not None:
            session_items = list(getattr(request.session, "items", []) or [])
            inferred = _session_dependency_services(session_items)

        selected_services = selected if selected is not None else inferred
        if "worker" in selected_services:
            worker_base_url = str(test_config.get("delivery_worker.base_url") or "").strip()
            if not worker_base_url:
                worker_port = test_config.get("delivery_worker.port")
                if worker_port not in (None, ""):
                    worker_base_url = f"http://127.0.0.1:{worker_port}"
            if worker_base_url:
                service_urls.append(("worker", worker_base_url))

        for service, key in (
            ("web", "web_server.base_url"),
            ("mcp", "mcp_server.base_url"),
            ("a2a", "a2a_server.base_url"),
        ):
            if service in selected_services:
                service_urls.append((service, str(test_config.get(key) or "").strip()))

    if selected is not None:
        service_urls = [(service, base_url) for service, base_url in service_urls if service in selected]
    return service_urls


@pytest.fixture(scope="session")
def test_config(request):
    """
    Load test configuration using config hierarchy:
    1. OS Environment Variables (CLOUD_DOG__NOTIFY__*)
    2. env file (from --env flag)
    3. config.yaml (if exists)
    4. defaults.yaml
    
    Gracefully fails if required settings are missing.
    """
    # Get env file from command line or environment
    env_args = _raw_env_args(request.config.getoption("--env"))
    if not env_args:
        pytest.fail(
            "❌ CRITICAL: --env file parameter is REQUIRED for all tests\n"
            "Specify with: pytest --env <env-file>\n"
        )
    try:
        env_paths = _resolve_env_paths(env_args)
    except FileNotFoundError as exc:
        pytest.fail(str(exc))
    primary_env_file = str(env_paths[0].resolve())
    env_values = _merge_env_values(env_paths)
    # Keep health-contract env_file aligned with server_control primary env input.
    env_values["CLOUD_DOG__NOTIFY__APP__ENV_FILE"] = primary_env_file
    runtime_mode, use_external_runtime, test_api_base_url, test_mcp_base_url = _resolve_runtime_contract(env_values)

    # Export the selected merged env contract into the pytest process so strict
    # RuntimeConfig(...) unit tests compile against the same environment that the
    # active --env file declares.
    previous_env: dict[str, str | None] = {}
    for key, value in env_values.items():
        previous_env[key] = os.environ.get(key)
        os.environ[key] = str(value)

    def _restore_selected_env() -> None:
        for key, previous in previous_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous

    request.addfinalizer(_restore_selected_env)

    # Runtime-mode contract is explicit and visible to all tests.
    os.environ["TEST_RUNTIME_MODE"] = runtime_mode
    os.environ["TEST_USE_EXTERNAL_RUNTIME"] = "true" if use_external_runtime else "false"
    if test_api_base_url:
        os.environ["TEST_API_BASE_URL"] = test_api_base_url
    if test_mcp_base_url:
        os.environ["TEST_MCP_BASE_URL"] = test_mcp_base_url

    os.environ["CLOUD_DOG__NOTIFY__TEST__RUNTIME_MODE"] = runtime_mode
    os.environ["CLOUD_DOG__NOTIFY__TEST__USE_EXTERNAL_RUNTIME"] = (
        "true" if use_external_runtime else "false"
    )
    if test_api_base_url:
        os.environ["CLOUD_DOG__NOTIFY__TEST__API_BASE_URL"] = test_api_base_url
    if test_mcp_base_url:
        os.environ["CLOUD_DOG__NOTIFY__TEST__MCP_BASE_URL"] = test_mcp_base_url
    
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="notify-combined-env-",
        delete=False,
    ) as fh:
        for key in sorted(env_values.keys()):
            fh.write(f"{key}={shlex.quote(str(env_values[key]))}\n")
        merged_env_path = Path(fh.name)
    request.addfinalizer(lambda: merged_env_path.unlink(missing_ok=True))
    # Load and refresh global config singleton with env file
    try:
        config = get_config(
            env_file=str(merged_env_path),
            load_env_file=True,
            force_reload=True,
        )
    except Exception as e:
        pytest.fail(
            f"Failed to load configuration from {primary_env_file}: {e}\n"
            f"Check that the env file is valid and accessible"
        )
    
    # Verify critical settings exist
    missing_settings = []
    
    # Check API server settings
    api_key = config.get("api_server.api_key")
    api_base_url = config.get("api_server.base_url")
    if not api_key:
        missing_settings.append("api_server.api_key")
    if not api_base_url:
        missing_settings.append("api_server.base_url")
    
    if missing_settings:
        pytest.fail(
            f"Missing required settings: {', '.join(missing_settings)}\n"
            f"Check your env file(s): {', '.join(str(p) for p in env_paths)}\n"
            f"Required settings should be in format: CLOUD_DOG__NOTIFY__API_SERVER__API_KEY=..."
        )
    
    return config


@pytest.fixture(scope="session")
def api_base_url(test_config):
    """Get API base URL from config"""
    url = test_config.get("api_server.base_url")
    if not url:
        pytest.fail("api_server.base_url not configured. Check your env file.")
    return url


@pytest.fixture(scope="session")
def api_key(test_config):
    """Get API key from config"""
    key = test_config.get("api_server.api_key")
    if not key:
        pytest.fail("api_server.api_key not configured. Check your env file.")
    return key


@pytest.fixture(scope="function")
def api_cleanup_registry(api_base_url, api_key, test_config):
    """Track created API resources for cleanup after each test."""
    timeout = test_config.get("api.timeout") or 300
    registry = ApiCleanupRegistry(
        base_url=api_base_url,
        api_key=api_key,
        timeout=float(timeout),
    )
    skip_cleanup = _truthy(os.environ.get("TEST_DISABLE_API_CLEANUP"))
    yield registry
    if not skip_cleanup:
        registry.cleanup()


@pytest.fixture(autouse=True)
def track_httpx_requests(monkeypatch, api_cleanup_registry, api_base_url):
    """Auto-track API resource creation for cleanup."""
    def _should_track(response: httpx.Response) -> bool:
        try:
            return str(response.request.url).startswith(api_base_url)
        except Exception:
            return False

    original_client_post = httpx.Client.post
    original_async_post = httpx.AsyncClient.post
    original_request = httpx.request

    def _client_post(self, *args, **kwargs):
        response = original_client_post(self, *args, **kwargs)
        if _should_track(response):
            api_cleanup_registry.track_response(response)
        return response

    async def _async_post(self, *args, **kwargs):
        response = await original_async_post(self, *args, **kwargs)
        if _should_track(response):
            api_cleanup_registry.track_response(response)
        return response

    def _request(method, url, *args, **kwargs):
        response = original_request(method, url, *args, **kwargs)
        if method.upper() == "POST" and _should_track(response):
            api_cleanup_registry.track_response(response)
        return response

    monkeypatch.setattr(httpx.Client, "post", _client_post)
    monkeypatch.setattr(httpx.AsyncClient, "post", _async_post)
    monkeypatch.setattr(httpx, "request", _request)


async def process_deliveries(db, job_manager, message_id=None, max_cycles=10, timeout=5.0):
    """
    Process queued deliveries using the DeliveryWorker for a bounded number of cycles.
    Skips gracefully if required delivery worker configuration is missing.
    """
    config = get_config()
    # External-runtime modes already have a worker in the runtime process.
    # Poll runtime API state directly because local DB handles may not point to
    # the same storage backend as the external runtime.
    use_external_runtime = _truthy(os.environ.get("TEST_USE_EXTERNAL_RUNTIME"))
    processed_cycles = 0
    deadline = time.monotonic() + float(timeout)

    try:
        from src.core.state_machine import DeliveryState
    except Exception as exc:
        raise RuntimeError(f"Delivery state dependencies unavailable: {exc}") from exc

    # Treat these as in-flight worker states when polling runtime API state.
    active_states = {
        DeliveryState.QUEUED.value,
        DeliveryState.FORMATTING.value,
        DeliveryState.SENDING.value,
    }
    processable_states = {
        DeliveryState.QUEUED.value,
        DeliveryState.SOFT_FAILED.value,
    }

    api_base_url = str(
        os.environ.get("TEST_API_BASE_URL")
        or config.get("api_server.base_url")
        or ""
    ).rstrip("/")
    api_key = (
        os.environ.get("TEST_API_KEY")
        or config.get("api_server.api_key")
        or ""
    )

    def _cancel_stale_queued_messages() -> None:
        if message_id is None or not api_base_url or not api_key:
            return
        headers = {"X-API-Key": str(api_key)}
        try:
            with httpx.Client(timeout=10.0) as client:
                list_resp = client.get(
                    f"{api_base_url}/messages",
                    headers=headers,
                    params={"status": "queued", "limit": 200},
                )
                if list_resp.status_code != 200:
                    return
                payload = list_resp.json()
                items = payload if isinstance(payload, list) else payload.get("items", [])
                for item in items:
                    stale_id = item.get("id") if isinstance(item, dict) else None
                    if stale_id is None or int(stale_id) == int(message_id):
                        continue
                    try:
                        client.post(f"{api_base_url}/messages/{int(stale_id)}/cancel", headers=headers)
                    except Exception:
                        pass
        except Exception:
            pass

    if use_external_runtime:
        if message_id is None:
            return processed_cycles

        if not api_base_url:
            pytest.fail("External runtime API base URL unavailable for delivery polling")
        if not api_key:
            pytest.fail("External runtime API key unavailable for delivery polling")

        headers = {"X-API-Key": str(api_key)}
        # External worker processing is asynchronous. Keep a small minimum wait
        # budget, but avoid large fixed delays that stall the full IT suite.
        external_timeout = max(float(timeout), 15.0)
        deadline = time.monotonic() + external_timeout

        # Keep external-runtime tests deterministic by cancelling stale queued
        # messages that can starve the newly created message under test.
        _cancel_stale_queued_messages()

        poll_interval = 0.5
        max_external_cycles = max(
            int(external_timeout / poll_interval) + 1,
            int(max_cycles),
        )

        while processed_cycles < max_external_cycles and time.monotonic() < deadline:
            try:
                with httpx.Client(timeout=min(float(timeout), 10.0)) as client:
                    resp = client.get(
                        f"{api_base_url}/messages/{message_id}/deliveries",
                        headers=headers,
                    )
                if resp.status_code == 200:
                    payload = resp.json()
                    items = payload.get("items", []) if isinstance(payload, dict) else []
                    if items and all(
                        d.get("state") not in active_states for d in items
                    ):
                        break
            except Exception:
                # Keep polling until timeout budget is exhausted.
                pass

            processed_cycles += 1
            await asyncio.sleep(poll_interval)

        return processed_cycles

    try:
        from src.core.delivery_worker import DeliveryWorker
        from src.database.repositories import DeliveryRepository
    except Exception as exc:
        pytest.skip(f"Delivery worker dependencies unavailable: {exc}")

    try:
        worker = DeliveryWorker(db, job_manager, config=config, poll_interval=0.1, batch_size=10)
    except Exception as exc:
        pytest.skip(f"Delivery worker unavailable: {exc}")

    delivery_repo = DeliveryRepository(db)

    # Local worker tests can also inherit stale queued messages from earlier
    # integration cases in the shared runtime database, which starves the
    # message under test under full-suite execution.
    _cancel_stale_queued_messages()

    while processed_cycles < max_cycles and time.monotonic() < deadline:
        target_deliveries = []
        if message_id is not None:
            target_deliveries = delivery_repo.get_by_message_id(message_id) or []
            # Local helper should only nudge the target message out of the queue.
            # Once the target delivery is formatting/sending/sent, the caller can
            # poll API state without re-entering unrelated stale deliveries.
            if target_deliveries and all(
                (d.get("state") or "") not in processable_states for d in target_deliveries
            ):
                break

        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0:
            break
        try:
            per_cycle_cap = float(
                os.environ.get("TEST_DELIVERY_PROCESS_CYCLE_TIMEOUT_SECONDS", "5")
            )
        except Exception:
            per_cycle_cap = 5.0
        if per_cycle_cap <= 0:
            per_cycle_cap = 5.0
        cycle_timeout = min(per_cycle_cap, remaining)
        if message_id is None:
            try:
                await asyncio.wait_for(worker._process_cycle(), timeout=cycle_timeout)
            except asyncio.TimeoutError:
                # Keep cycling within the global timeout budget so one slow delivery
                # does not block processing of other queued deliveries.
                processed_cycles += 1
                await asyncio.sleep(0.1)
                continue
        else:
            pending_target = [
                d for d in target_deliveries
                if (d.get("state") or "") in processable_states
            ]
            if not pending_target:
                break

            for delivery in pending_target:
                if worker._should_retry_llm(delivery):
                    continue
                try:
                    await asyncio.wait_for(
                        worker._process_delivery(delivery),
                        timeout=cycle_timeout,
                    )
                except asyncio.TimeoutError:
                    break
                except Exception as exc:
                    error_text = str(exc)
                    permanent_not_found = (" not found" in error_text) and (
                        "Channel " in error_text or "Message " in error_text
                    )
                    is_transient = not (
                        error_text.startswith("No adapter found for channel")
                        or permanent_not_found
                    )
                    worker.job_manager.handle_delivery_failure(
                        delivery_id=delivery["id"],
                        error=error_text,
                        is_transient=is_transient,
                    )

        processed_cycles += 1
        await asyncio.sleep(0.1)

    return processed_cycles


@pytest.fixture(scope="session")
def web_base_url(test_config):
    """
    Get Web UI base URL from config (RULES.md: no hardcoded URLs in tests).
    """
    url = test_config.get("web_server.base_url")
    if not url:
        pytest.fail("web_server.base_url not configured. Check your env file.")
    return url


@pytest.fixture(scope="session")
def a2a_base_url(test_config):
    """Get A2A base URL from config"""
    url = test_config.get("a2a_server.base_url")
    if not url:
        pytest.fail("a2a_server.base_url not configured. Check your env file.")
    return url


@pytest.fixture(scope="session")
def default_channel(test_config):
    """Get default channel from config"""
    channel = test_config.get("default_channel")
    if not channel:
        pytest.fail("default_channel not configured. Check your env file.")
    return channel


@pytest.fixture(scope="session")
def storage_base_url(test_config):
    """Get storage base URL from config"""
    url = test_config.get("storage.local.base_url") or test_config.get("storage.base_url")
    if not url:
        pytest.fail("storage base_url not configured. Check your env file.")
    return url

@pytest.fixture(scope="session")
def smtp_config(test_config):
    """Get SMTP configuration from config"""
    smtp = test_config.get("channels.smtp.default", {})
    
    required = ["host", "port", "username", "password", "from_address"]
    missing = [k for k in required if not smtp.get(k)]
    
    if missing:
        pytest.skip(
            f"SMTP credentials missing: {', '.join(missing)}\n"
            f"Configure in env file with: CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__*"
        )
    
    return smtp


@pytest.fixture(scope="session")
def slack_config(test_config):
    """Get Slack webhook configuration from config"""
    slack = test_config.get("channels.chat_rest.transparentbordes", {})
    
    if not slack.get("endpoint"):
        pytest.skip(
            "Slack webhook endpoint not configured\n"
            "Configure in env file with: CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__ENDPOINT=..."
        )
    
    # Add channel_name from config if available
    channel_name = test_config.get("test.slack_channel_name") or test_config.get("channels.chat_rest.default.name")
    if channel_name:
        slack["channel_name"] = channel_name
    
    return slack


@pytest.fixture(scope="session")
def test_email(test_config):
    """Get test email address from config"""
    email = test_config.get("test.email")
    if not email:
        pytest.fail(
            "test.email not configured. "
            "Add CLOUD_DOG__NOTIFY__TEST__EMAIL=gary+notification-test@cloud-dog.net to your env file (e.g., private/env-test)"
        )
    return email


@pytest.fixture(scope="session")
def test_email_domain(test_config):
    """Get test email domain from config for synthetic addresses."""
    domain = test_config.get("test.email_domain", "@cloud-dog.net")
    return str(domain)


@pytest.fixture(scope="function")
def db():
    """
    Provide an isolated sqlite database for integration/unit paths that
    exercise repositories/managers directly (without API transport).
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name

    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    if not db_manager.connect():
        pytest.fail(f"Failed to connect temporary database: {db_uri}")
    db_manager.initialize_schema()

    try:
        yield db_manager
    finally:
        db_manager.disconnect()
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture(scope="function")
def job_manager(db):
    """Shared JobManager fixture for test paths that process delivery queues."""
    return JobManager(db=db)


def _sqlite_path_from_uri(db_uri: str) -> Path | None:
    db_path = str(db_uri or "").replace("sqlite:///", "").replace("sqlite3:///", "")
    if not db_path:
        return None
    return Path(db_path)


def _sqlite_table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _sqlite_table_has_column(conn, table_name: str, column_name: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return False
    return any(str(row[1]) == column_name for row in rows)


def _cleanup_sqlite_rows_created_since(test_config, started_at: str) -> None:
    db_uri = str(test_config.get("db.uri") or "")
    if "notify" not in db_uri and "notification" not in db_uri:
        return
    db_path = _sqlite_path_from_uri(db_uri)
    if db_path is None or not db_path.exists():
        return

    import sqlite3

    preserved_channels = {
        str(test_config.get("default_channel") or "").strip(),
        "email_default",
        "loopback_test",
        "chat_rest_transparentbordes",
    }
    preserved_channels.discard("")

    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        for table in (
            "job_call_logs",
            "job_callbacks",
            "job_deliveries",
            "receipts",
            "deliveries",
            "messages",
            "audit_events",
            "media_files",
            "notification_storage",
            "jobs",
            "group_members",
            "groups",
            "users",
            "prompts",
        ):
            if _sqlite_table_exists(conn, table) and _sqlite_table_has_column(conn, table, "created_at"):
                conn.execute(f"DELETE FROM {table} WHERE created_at >= ?", (started_at,))
        if _sqlite_table_exists(conn, "channels") and _sqlite_table_has_column(conn, "created_at"):
            placeholders = ",".join("?" for _ in preserved_channels)
            if placeholders:
                conn.execute(
                    f"DELETE FROM channels WHERE created_at >= ? AND name NOT IN ({placeholders})",
                    (started_at, *sorted(preserved_channels)),
                )
            else:
                conn.execute("DELETE FROM channels WHERE created_at >= ?", (started_at,))
        conn.commit()
        try:
            conn.execute("VACUUM")
        except Exception:
            pass
        conn.close()
    except Exception:
        return


@pytest.fixture(autouse=True, scope="module")
def _module_db_cleanup(request, test_config):
    """Clean rows for isolated fast modules without touching server-managed tiers."""
    module_path = Path(str(getattr(request.node, "fspath", "")))
    module_parts = set(module_path.parts)
    if "no_runtime_dependency" not in request.node.keywords and "fast" not in module_parts:
        yield
        return

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    yield
    _cleanup_sqlite_rows_created_since(test_config, started_at)




@pytest.fixture(scope="session", autouse=True)
def _clean_test_database_on_start(test_config):
    """Truncate accumulated test data at session start to prevent OOM from SQLite bloat.

    W28A-93a: Jobs/deliveries/messages accumulate across test runs. A 7MB+ DB
    with thousands of rows causes SQLite page cache to consume 35MB+ across
    5 server processes. Clean at session start to keep DB < 500KB.
    """
    db_uri = test_config.get("db.uri") or ""
    if "notify" not in str(db_uri) and "notification" not in str(db_uri):
        return
    import sqlite3
    from pathlib import Path
    db_path = str(db_uri).replace("sqlite:///", "").replace("sqlite3:///", "")
    if not db_path or not Path(db_path).exists():
        return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        for table in ["jobs", "job_call_logs", "job_callbacks", "job_deliveries",
                       "deliveries", "messages", "receipts", "audit_events",
                       "media_files", "notification_storage"]:
            try:
                conn.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc).lower():
                    raise
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        pass
    finally:
        if conn is not None:
            conn.close()


@pytest.fixture(scope="session", autouse=True)
def check_dependencies(test_config: RuntimeConfig, request):
    """
    Ensures selected external dependencies are configured and reachable before tests run.
    """
    env_args = _raw_env_args(request.config.getoption("--env"))
    if not env_args:
        pytest.fail("API dependency checks require --env to manage server lifecycle")
    try:
        env_paths = _resolve_env_paths(env_args)
    except FileNotFoundError as exc:
        pytest.fail(str(exc))
    primary_env_file = str(env_paths[0].resolve())
    env_values = _merge_env_values(env_paths)
    env_overrides = env_values
    runtime_mode, use_external_runtime, test_api_base_url, _ = _resolve_runtime_contract(env_values)
    test_env_tier = str(env_values.get("TEST_ENV_TIER") or "").strip().upper()
    session_items = list(getattr(request.session, "items", []) or [])
    llm_dependency_required = _session_requires_llm_dependency(session_items)
    skip_llm_dependency = (
        not llm_dependency_required
        or _all_items_marked(session_items, _NO_LLM_DEPENDENCY_MARKER)
        or test_env_tier in {"UT", "QT"}
    )
    skip_runtime_dependency = _all_items_marked(session_items, _NO_RUNTIME_DEPENDENCY_MARKER)

    missing_settings = []

    api_key = test_config.get("api_server.api_key")
    api_base_url = test_config.get("api_server.base_url")
    if not api_key:
        missing_settings.append("api_server.api_key")
    if not api_base_url:
        missing_settings.append("api_server.base_url")

    llm_provider = test_config.get("llm.provider")
    llm_base_url = test_config.get("llm.base_url")
    llm_model = test_config.get("llm.model")
    if not skip_llm_dependency:
        if not llm_provider:
            missing_settings.append("llm.provider")
        if not llm_base_url:
            missing_settings.append("llm.base_url")
        if not llm_model:
            missing_settings.append("llm.model")

    if missing_settings:
        pytest.fail(
            f"Missing critical configuration for dependencies: {', '.join(missing_settings)}\n"
            "Please ensure these are set in your env file (for example private/env-test)."
        )

    resolved_api_base_url = test_api_base_url or str(api_base_url).strip()

    def _api_health_payload() -> dict | None:
        return _health_payload(resolved_api_base_url, timeout=5.0)

    payload = _api_health_payload()
    payload_env = str((payload or {}).get("env_file") or "")

    if runtime_mode == "local-server":
        if skip_runtime_dependency or test_env_tier == "QT":
            print("\n[Dependency Check] Skipping local runtime startup for no_runtime_dependency/QT selection.")
            return
        service_urls = _dependency_service_urls(
            test_config,
            include_web_mcp_a2a=(test_env_tier != "UT"),
            request=request,
        )
        for service, base_url in service_urls:
            if not base_url:
                continue

            # For UT tier: accept any healthy API server without restarting.
            # UT tests need a running API for DB/fixture setup but do not
            # require a specific env_file — they construct their own configs.
            if (
                test_env_tier == "UT"
                and payload is not None
                and _api_key_is_accepted(resolved_api_base_url, str(api_key))
            ):
                print(
                    f"\n[Dependency Check] UT tier: {service} already healthy, skipping restart."
                )
                continue

            current_health = _health_payload(base_url, timeout=5.0)
            if current_health is None:
                current_health = _wait_for_health(base_url, timeout_seconds=60.0)
            if current_health is None and service in {"api", "web", "mcp", "a2a", "worker"}:
                if _api_key_is_accepted(resolved_api_base_url, str(api_key), timeout=10.0) or _tcp_port_is_open(base_url):
                    current_health = {"env_file": primary_env_file, "status": "ok"}
            current_env = str((current_health or {}).get("env_file") or "")
            current_matches = current_health is not None and (
                not current_env or current_env == primary_env_file
            )

            if current_matches:
                print(
                    f"\n[Dependency Check] {service} already healthy"
                    + (
                        f" with env {current_env}, skipping restart."
                        if service == "api" and current_env
                        else ", skipping restart."
                    )
                )
                health = current_health
            else:
                print(
                    f"\n[Dependency Check] Enforcing local-server runtime for {service} via server_control.sh stop/start {service}..."
                )
                _restart_local_service(primary_env_file, service, env_overrides)
                health = _wait_for_health(base_url, timeout_seconds=60.0)
            if health is None:
                pytest.fail(
                    f"{service} dependency not reachable at {base_url}/health after local-server stop/start"
                )

            if service == "api":
                payload_env = str((health or {}).get("env_file") or "")
                if payload_env and payload_env != primary_env_file:
                    pytest.fail(
                        f"API dependency running with wrong env_file: expected {primary_env_file}, got {payload_env}"
                    )
                api_key = str(test_config.get("api_server.api_key") or "").strip()
                cancelled = _cancel_stale_queued_messages(resolved_api_base_url, api_key)
                if cancelled:
                    print(
                        f"[Dependency Check] Cancelled {cancelled} stale queued message(s) before {test_env_tier or 'runtime'} execution."
                    )
    elif use_external_runtime and test_env_tier == "QT":
        print("\n[Dependency Check] Skipping external runtime check for QT static quality selection.")
    elif use_external_runtime:
        if payload is None:
            pytest.exit(
                f"BLOCKED: TEST_RUNTIME_MODE={runtime_mode} requires external API runtime, but "
                f"{resolved_api_base_url}/health is unreachable",
                returncode=2,
            )
    else:
        service_urls = _dependency_service_urls(
            test_config,
            include_web_mcp_a2a=(test_env_tier != "UT"),
            request=request,
        )
        for service, base_url in service_urls:
            if not base_url:
                continue
            current_health = _health_payload(base_url, timeout=5.0)
            current_env = str((current_health or {}).get("env_file") or "")
            current_matches = current_health is not None and (
                not current_env or current_env == primary_env_file
            )

            if current_matches:
                print(
                    f"\n[Dependency Check] {service} already healthy"
                    + (
                        f" with env {current_env}, skipping restart."
                        if service == "api" and current_env
                        else ", skipping restart."
                    )
                )
                health = current_health
            else:
                print(
                    f"\n[Dependency Check] Enforcing local-server runtime for {service} via server_control.sh stop/start {service}..."
                )
                _restart_local_service(primary_env_file, service, env_overrides)
                health = _wait_for_health(base_url, timeout_seconds=60.0)
            if health is None:
                pytest.fail(
                    f"{service} dependency not reachable at {base_url}/health after local-server stop/start"
                )

            if service == "api":
                payload_env = str((health or {}).get("env_file") or "")
                if payload_env and payload_env != primary_env_file:
                    pytest.fail(
                        f"API dependency running with wrong env_file: expected {primary_env_file}, got {payload_env}"
                    )
                if test_env_tier == "UT":
                    api_key = str(test_config.get("api_server.api_key") or "").strip()
                    cancelled = _cancel_stale_queued_messages(resolved_api_base_url, api_key)
                    if cancelled:
                        print(
                            f"[Dependency Check] Cancelled {cancelled} stale queued message(s) before UT execution."
                        )
    if skip_llm_dependency:
        print(
            "[Dependency Check] Skipping LLM dependency checks for "
            "selection without LLM capability/no_llm_dependency/UT/QT."
        )
    else:
        from src.core.llm.runtime_client import LLMManager

        print(f"\n[Dependency Check] Checking LLM provider '{llm_provider}' model '{llm_model}'...")
        llm_manager = LLMManager(test_config)
        if not llm_manager.connect() or not llm_manager.get_llm():
            message = (
                f"LLM dependency not reachable at {llm_base_url} for provider {llm_provider} model {llm_model}"
            )
            if use_external_runtime:
                pytest.exit(f"BLOCKED: {message}", returncode=2)
            pytest.fail(message)
        try:
            print("[Dependency Check] Warming LLM runtime...")
            _warm_llm_runtime(llm_manager, test_config)
        except Exception as exc:
            message = (
                f"LLM dependency warm-up failed for provider {llm_provider} model {llm_model}: {exc}"
            )
            if use_external_runtime:
                pytest.exit(f"BLOCKED: {message}", returncode=2)
            pytest.fail(message)

    print("[Dependency Check] All critical dependencies configured.")
