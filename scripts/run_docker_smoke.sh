#!/bin/bash
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

set -e

DRY_RUN=0
ENV_BASE="private/env-docker-local-smoke"

if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
elif [ -n "${1:-}" ]; then
    ENV_BASE="$1"
    if [ "${2:-}" = "--dry-run" ]; then
        DRY_RUN=1
    fi
fi

ENV_STREAMABLE="${ENV_BASE}-streamable"
ENV_JSONRPC="${ENV_BASE}-jsonrpc"
ENV_LEGACY="${ENV_BASE}-legacy-sse"
ENV_ASYNC="${ENV_BASE}-async"
ENV_STDIO="${ENV_BASE}-stdio"

IMAGE=${DOCKER_IMAGE:-cloud-dog/notification-agent-mcp-server:latest}
CONTAINER=${DOCKER_CONTAINER:-notify-all}
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CERT_BUNDLE="${CERT_BUNDLE:-}"

PYTHON="python3"
if [ -f "./.venv/bin/python3" ]; then
    PYTHON="./.venv/bin/python3"
fi

if [ ! -f "${ENV_BASE}" ] && [ "${DRY_RUN}" -ne 1 ]; then
    echo "CRITICAL: Missing env file: ${ENV_BASE}"
    echo "Copy docker-env.example -> private/env-docker-local-smoke and set credentials."
    exit 1
fi

generate_variants() {
    ROOT_DIR="${ROOT_DIR}" ENV_BASE="${ENV_BASE}" ${PYTHON} - <<'PY'
import os
from pathlib import Path

def load_env(path: Path):
    data = {}
    for line in path.read_text().splitlines():
        if not line or line.lstrip().startswith('#'):
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value
    return data

root = Path(os.environ.get("ROOT_DIR", Path.cwd()))
base_path = Path(os.environ.get("ENV_BASE", "private/env-docker-local-smoke"))
if not base_path.is_absolute():
    base_path = root / base_path
data = load_env(base_path)

variants = {
    "streamable": {
        "CLOUD_DOG__NOTIFY__MCP_SERVER__TRANSPORT": "streamable_http",
        "CLOUD_DOG__NOTIFY__MCP_SERVER__ASYNC_JOBS_ENABLED": "false",
    },
    "jsonrpc": {
        "CLOUD_DOG__NOTIFY__MCP_SERVER__TRANSPORT": "http_jsonrpc",
        "CLOUD_DOG__NOTIFY__MCP_SERVER__ASYNC_JOBS_ENABLED": "false",
    },
    "legacy-sse": {
        "CLOUD_DOG__NOTIFY__MCP_SERVER__TRANSPORT": "legacy_sse",
        "CLOUD_DOG__NOTIFY__MCP_SERVER__ASYNC_JOBS_ENABLED": "false",
    },
    "async": {
        "CLOUD_DOG__NOTIFY__MCP_SERVER__TRANSPORT": "http_jsonrpc",
        "CLOUD_DOG__NOTIFY__MCP_SERVER__ASYNC_JOBS_ENABLED": "true",
    },
    "stdio": {
        "CLOUD_DOG__NOTIFY__MCP_SERVER__TRANSPORT": "stdio",
        "CLOUD_DOG__NOTIFY__MCP_SERVER__ASYNC_JOBS_ENABLED": "false",
    },
}

for suffix, overrides in variants.items():
    env = dict(data)
    env.update(overrides)
    env["CLOUD_DOG__NOTIFY__TEST__MCP_DOCKER_ENV_LOADED"] = "true"
    if suffix == "stdio":
        env["CLOUD_DOG__NOTIFY__TEST__MCP_STDIO_ENV_FILE"] = str(base_path.parent / f"{base_path.name}-stdio")
    out_path = base_path.parent / f"{base_path.name}-{suffix}"
    lines = ["# Auto-generated docker smoke env", f"# Variant: {suffix}", ""]
    for key in sorted(env.keys()):
        lines.append(f"{key}={env[key]}")
    lines.append("")
    out_path.write_text("\n".join(lines))
    print(f"Wrote {out_path}")
PY
}

if [ ! -f "${ENV_STREAMABLE}" ] || [ ! -f "${ENV_JSONRPC}" ] || [ ! -f "${ENV_LEGACY}" ] || [ ! -f "${ENV_ASYNC}" ] || [ ! -f "${ENV_STDIO}" ]; then
    echo "Generating MCP transport env variants..."
    generate_variants
fi

wait_for_api() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "DRY RUN: wait_for_api $1"
        return 0
    fi
    local env_file="$1"
    local port
    port=$(grep -E '^CLOUD_DOG__NOTIFY__API_SERVER__PORT=' "${env_file}" | tail -1 | cut -d= -f2- | sed 's/^\"//; s/\"$//' | xargs || true)
    if [ -z "${port}" ]; then
        echo "Missing CLOUD_DOG__NOTIFY__API_SERVER__PORT in ${env_file}"
        return 1
    fi
    for _ in $(seq 1 30); do
        if curl -fs "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "API health check failed after waiting: http://127.0.0.1:${port}/health"
    return 1
}

wait_for_mcp() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "DRY RUN: wait_for_mcp $1"
        return 0
    fi
    local env_file="$1"
    local port transport
    transport=$(grep -E '^CLOUD_DOG__NOTIFY__MCP_SERVER__TRANSPORT=' "${env_file}" | tail -1 | cut -d= -f2- | sed 's/^\"//; s/\"$//' | xargs || true)
    if [ "${transport}" = "stdio" ]; then
        return 0
    fi
    port=$(grep -E '^CLOUD_DOG__NOTIFY__MCP_SERVER__PORT=' "${env_file}" | tail -1 | cut -d= -f2- | sed 's/^\"//; s/\"$//' | xargs || true)
    if [ -z "${port}" ]; then
        echo "Missing CLOUD_DOG__NOTIFY__MCP_SERVER__PORT in ${env_file}"
        return 1
    fi
    for _ in $(seq 1 30); do
        if curl -fs "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "MCP health check failed after waiting: http://127.0.0.1:${port}/health"
    return 1
}

start_container() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "DRY RUN: docker rm -f ${CONTAINER}"
        echo "DRY RUN: docker run -d --name ${CONTAINER} --network=host ... ${IMAGE}"
        echo "DRY RUN: using env ${1}"
        return 0
    fi
    local env_file="$1"
    local cert_mount=()
    if [ -f "${CERT_BUNDLE}" ]; then
        cert_mount=(-v "${CERT_BUNDLE}:/app/certs/trusted-ca-bundle.pem:ro")
    fi
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    docker run -d --name "${CONTAINER}" --network=host \
        -v "${ROOT_DIR}/private/$(basename "${env_file}"):/app/env:ro" \
        -v "${ROOT_DIR}/logs:/app/logs" \
        -v "${ROOT_DIR}/database:/app/database" \
        -v "${ROOT_DIR}/storage:/app/storage" \
        -v "${ROOT_DIR}/cache:/app/cache" \
        "${cert_mount[@]}" \
        "${IMAGE}" >/dev/null
    wait_for_api "${env_file}"
    wait_for_mcp "${env_file}"
}

stop_container() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "DRY RUN: docker rm -f ${CONTAINER}"
        return 0
    fi
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
}

run_pytest() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "DRY RUN: ${PYTHON} -m pytest --env \"$1\" $2 -v -x"
        return 0
    fi
    ${PYTHON} -m pytest --env "$1" "$2" -v -x
}

echo "Running docker smoke tests (container: ${CONTAINER}, image: ${IMAGE})"

start_container "${ENV_STREAMABLE}"
run_pytest "${ENV_STREAMABLE}" tests/system/ST1.19_StartupServices
run_pytest "${ENV_STREAMABLE}" tests/integration/IT1.20_MCP_StreamableHTTP
stop_container

start_container "${ENV_JSONRPC}"
run_pytest "${ENV_JSONRPC}" tests/integration/IT1.21_MCP_HTTP_JSONRPC
stop_container

start_container "${ENV_LEGACY}"
run_pytest "${ENV_LEGACY}" tests/integration/IT1.22_MCP_LegacySSE
stop_container

start_container "${ENV_ASYNC}"
run_pytest "${ENV_ASYNC}" tests/integration/IT1.23_MCP_AsyncJobs
run_pytest "${ENV_STDIO}" tests/integration/IT1.24_MCP_Stdio
run_pytest "${ENV_ASYNC}" tests/integration/IT1.12_RealChannelAdapters
run_pytest "${ENV_ASYNC}" tests/application/AT1.17_EmailValidation
run_pytest "${ENV_ASYNC}" tests/integration/IT1.4_WebUIEndpoints
run_pytest "${ENV_ASYNC}" tests/integration/IT1.5_WebUILinks
stop_container
