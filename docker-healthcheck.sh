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

ENV_FILE="/app/env"

if [ ! -f "${ENV_FILE}" ]; then
    echo "Missing env file: ${ENV_FILE}"
    exit 1
fi

API_PORT=$(grep -E '^CLOUD_DOG__NOTIFY__API_SERVER__PORT=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | sed 's/^"//; s/"$//' | xargs || true)
if [ -z "${API_PORT}" ]; then
    echo "Missing CLOUD_DOG__NOTIFY__API_SERVER__PORT in ${ENV_FILE}"
    exit 1
fi

WORKER_ENABLED=$(grep -E '^CLOUD_DOG__NOTIFY__DELIVERY_WORKER__ENABLED=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | sed 's/^"//; s/"$//' | xargs || true)
WORKER_PORT=$(grep -E '^CLOUD_DOG__NOTIFY__DELIVERY_WORKER__PORT=' "${ENV_FILE}" | tail -1 | cut -d= -f2- | sed 's/^"//; s/"$//' | xargs || true)
if [ -z "${WORKER_PORT}" ]; then
    WORKER_PORT=8024
fi

curl -fs "http://127.0.0.1:${API_PORT}/health" > /dev/null

case "${WORKER_ENABLED}" in
    false|False|0|no|NO|off|OFF)
        ;;
    *)
        curl -fs "http://127.0.0.1:${WORKER_PORT}/worker/health" > /dev/null
        ;;
esac
