#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${VAULT_ADDR:-}" || -z "${VAULT_TOKEN:-}" ]]; then
  echo "ERROR: VAULT_ADDR/VAULT_TOKEN are not set. Source env-vault first." >&2
  echo "Hint: set -a; source /opt/iac/Development/cloud-dog-ai/env-vault; set +a" >&2
  exit 2
fi

required_envs=(
  "tests/env-local-docker-server"
  "tests/env-AT-local-docker-vault-8020"
  "tests/env-IT-runtime-external-8020"
)

missing=0
for f in "${required_envs[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "MISSING: $f"
    missing=1
  else
    echo "OK: $f"
  fi
done

if [[ $missing -ne 0 ]]; then
  exit 3
fi

echo "Vault bootstrap variables detected and required env overlays are present."
