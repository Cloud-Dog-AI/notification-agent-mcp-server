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

APP_DIR="/app"
ENV_FILE="/app/env"

echo "============================================================================"
echo "Notification Agent MCP Server - Docker Entrypoint"
echo "============================================================================"
echo "Mode: ${1:-all}"
echo "Working Directory: ${APP_DIR}"
echo "============================================================================"

mkdir -p "${APP_DIR}/logs" "${APP_DIR}/cache" "${APP_DIR}/database" "${APP_DIR}/storage" "${APP_DIR}/working" "${APP_DIR}/certs"

if [ ! -f "${ENV_FILE}" ]; then
    echo "CRITICAL: Missing env file at ${ENV_FILE}"
    echo "Mount an env file with: -v /path/to/private/env-docker-local-smoke:/app/env:ro"
    echo "See docker-env.example for required settings."
    exit 1
fi

chmod +x "${APP_DIR}/server_control.sh"

touch "${APP_DIR}/logs/api_server.log" \
      "${APP_DIR}/logs/delivery_worker.log" \
      "${APP_DIR}/logs/web_server.log" \
      "${APP_DIR}/logs/mcp_server.log" \
      "${APP_DIR}/logs/a2a_server.log"

start_and_tail() {
    local target="$1"
    echo "Starting ${target} via server_control.sh (env: ${ENV_FILE})"
    "${APP_DIR}/server_control.sh" --env "${ENV_FILE}" start "${target}"
    echo "Tailing logs..."
    tail -F "${APP_DIR}"/logs/*.log 2>/dev/null || sleep infinity
}

case "${1:-all}" in
    all)
        start_and_tail all
        ;;
    api|worker|web|mcp|a2a)
        start_and_tail "$1"
        ;;
    status)
        "${APP_DIR}/server_control.sh" --env "${ENV_FILE}" status all
        ;;
    stop)
        "${APP_DIR}/server_control.sh" --env "${ENV_FILE}" stop all
        ;;
    shell|bash)
        exec /bin/bash
        ;;
    help|--help|-h)
        echo "Usage: docker run <image> [all|api|worker|web|mcp|a2a|status|stop|shell]"
        exit 0
        ;;
    *)
        echo "Unknown mode: $1"
        echo "Use: all|api|worker|web|mcp|a2a|status|stop|shell"
        exit 1
        ;;
esac
