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

set -euo pipefail

# ── Variant selector (PS-97 v1.1 §1.1.3 / W28A-861-R3 §4) ─────────
#   --variant public  (default) builds Dockerfile.public for the public boundary
#                      (single public index, default https://pypi.org/simple).
#   --variant dev      builds the internal Dockerfile; set PYPI_URL to the
#                      internal staging boundary index for that build.
# Usage: docker-build.sh [VERSION] [--variant public|dev]
VARIANT="${PUBLICATION_BUILD_VARIANT:-public}"
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --variant)
      VARIANT="${2:-public}"
      shift 2 ;;
    --variant=*)
      VARIANT="${1#*=}"
      shift ;;
    *)
      POSITIONAL+=("$1")
      shift ;;
  esac
done
set -- "${POSITIONAL[@]}"

case "${VARIANT}" in
  dev|public) ;;
  *)
    echo "ERROR: --variant must be 'dev' or 'public' (got: ${VARIANT})" >&2
    exit 2 ;;
esac

DOCKERFILE="Dockerfile"
if [[ "${VARIANT}" == "public" ]]; then
  DOCKERFILE="Dockerfile.public"
fi
if [[ ! -f "${DOCKERFILE}" ]]; then
  echo "ERROR: ${DOCKERFILE} not found (variant=${VARIANT})" >&2
  exit 2
fi

VERSION=${1:-latest}
CONTAINER=notification-agent-mcp-server
FOLDER=cloud-dog
REGISTRY="${REGISTRY:-}"
CUSTOM_CA_CERT=${CUSTOM_CA_CERT:-/usr/local/share/ca-certificates/cloud-dog.net.ca.crt}

LOG_DIR="working"
LOG_FILE="${LOG_DIR}/docker-build.log"
CERT_DIR="certs"
CERT_FILE="${CERT_DIR}/ca.crt"
PIP_CONF=".pip.conf.build"

# ── Publication tag isolation (W28A-831) ──────────────────────────
# PUBLICATION_TAG_SUFFIX appends an isolation suffix (e.g. boundary-test)
# so publication test images never collide with dev/
# release tags. Empty (the default) leaves behaviour unchanged.
PUBLICATION_TAG_SUFFIX="${PUBLICATION_TAG_SUFFIX:-}"
if [[ -n "${PUBLICATION_TAG_SUFFIX}" ]]; then
  if [[ ! "${PUBLICATION_TAG_SUFFIX}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "ERROR: PUBLICATION_TAG_SUFFIX must match ^[a-z0-9]([a-z0-9-]*[a-z0-9])?\$ (got: '${PUBLICATION_TAG_SUFFIX}')" >&2
    exit 2
  fi
  case "${PUBLICATION_TAG_SUFFIX}" in
    latest|dev|prod|release|stable)
      echo "ERROR: PUBLICATION_TAG_SUFFIX '${PUBLICATION_TAG_SUFFIX}' is reserved" >&2
      exit 2 ;;
  esac
  EFFECTIVE_TAG="${VERSION}-${PUBLICATION_TAG_SUFFIX}"
  echo "Publication test build: tag suffix '-${PUBLICATION_TAG_SUFFIX}' (internal registry tag will be skipped)."
else
  EFFECTIVE_TAG="${VERSION}"
fi

# Default index per boundary (W28A-861-R3 §4):
#   public -> single public index (https://pypi.org/simple), single --index-url
#   dev    -> set PYPI_URL to the internal staging boundary index (no default host
#             baked into this published script)
if [[ "${VARIANT}" == "public" ]]; then
  PYPI_URL="${PYPI_URL:-https://pypi.org/simple}"
else
  PYPI_URL="${PYPI_URL:-}"
  if [[ -z "${PYPI_URL}" ]]; then
    echo "ERROR: --variant dev requires PYPI_URL set to the internal staging index" >&2
    exit 2
  fi
fi
PYPI_USERNAME="${PYPI_USERNAME:-}"
PYPI_PASSWORD="${PYPI_PASSWORD:-}"

mkdir -p "${LOG_DIR}"
mkdir -p "${CERT_DIR}"

if [[ "${VARIANT}" == "public" ]]; then
    # Public boundary: STRICT single index (PS-97 §3.3) — one index-url only.
    if [[ -n "${PYPI_USERNAME}" && -n "${PYPI_PASSWORD}" ]]; then
        cat > "${PIP_CONF}" << EOF
[global]
index-url = https://${PYPI_USERNAME}:${PYPI_PASSWORD}@${PYPI_URL#https://}
EOF
    else
        cat > "${PIP_CONF}" << EOF
[global]
index-url = ${PYPI_URL}
EOF
    fi
elif [[ -n "${PYPI_USERNAME}" && -n "${PYPI_PASSWORD}" ]]; then
    cat > "${PIP_CONF}" << EOF
[global]
index-url = https://${PYPI_USERNAME}:${PYPI_PASSWORD}@${PYPI_URL#https://}
trusted-host = $(python3 -c "from urllib.parse import urlsplit; print(urlsplit('${PYPI_URL}').hostname)")
EOF
else
    cat > "${PIP_CONF}" << EOF
[global]
index-url = ${PYPI_URL}
trusted-host = $(python3 -c "from urllib.parse import urlsplit; print(urlsplit('${PYPI_URL}').hostname)")
EOF
fi
chmod 600 "${PIP_CONF}"

# The pre-build publish-before-pin guard can intentionally fail before Docker
# starts.  Its failure must not strand the generated credential-bearing pip
# configuration (or the transient CA copy) in the worktree.
cleanup_generated_build_files() {
  rm -f "${PIP_CONF}"
  rm -f "${CERT_FILE}"
}
trap cleanup_generated_build_files EXIT

echo "=========================================="
echo "Docker Build Configuration"
echo "=========================================="
echo "Variant: ${VARIANT} (dockerfile=${DOCKERFILE})"
echo "Container: ${FOLDER}/${CONTAINER}:${VERSION}"
PYPI_HOST="$(python3 -c "from urllib.parse import urlsplit; print(urlsplit('${PYPI_URL}').hostname or 'configured-index')")"
echo "Index host: ${PYPI_HOST} (credentials redacted)"
echo "Network: host (build)"
echo "Log: ${LOG_FILE}"
echo "CA Cert (optional): ${CUSTOM_CA_CERT}"
echo "=========================================="
echo ""

# Copy CA certificate to build context if it exists (ignored by git).
# Public boundary builds use only the system trust store — no private CA overlay.
if [[ "${VARIANT}" == "dev" ]] && [ -f "${CUSTOM_CA_CERT}" ]; then
    echo "Copying CA certificate to ${CERT_FILE}"
    cp "${CUSTOM_CA_CERT}" "${CERT_FILE}"
    echo "✓ CA certificate copied"
elif [[ "${VARIANT}" == "public" ]]; then
    echo "Public variant: skipping private CA overlay (system trust store only)."
else
    echo "WARNING: CA certificate not found at ${CUSTOM_CA_CERT}"
    echo "Build will proceed without custom CA"
fi
echo ""

if [[ -n "${PUBLICATION_DRY_RUN:-}" ]]; then
  echo "DRY-RUN: build tag = ${FOLDER}/${CONTAINER}:${EFFECTIVE_TAG}"
  if [[ -n "${REGISTRY}" && -z "${PUBLICATION_TAG_SUFFIX}" ]]; then
    echo "DRY-RUN: registry tag = ${REGISTRY}/${FOLDER}/${CONTAINER}:${EFFECTIVE_TAG}"
  elif [[ -n "${PUBLICATION_TAG_SUFFIX}" ]]; then
    echo "DRY-RUN: registry tag = (skipped — publication suffix '${PUBLICATION_TAG_SUFFIX}' set)"
  else
    echo "DRY-RUN: registry tag = (skipped; set REGISTRY to tag a registry image)"
  fi
  exit 0
fi

# For the public variant, pass the active public index to the Dockerfile so the
# single index-url install resolves there (one index only; nothing extra).
PUBLIC_INDEX_ARGS=()
if [[ "${VARIANT}" == "public" ]]; then
  PUBLIC_INDEX_ARGS=(--build-arg PIP_INDEX_URL="${PYPI_URL}")
else
  PUBLIC_INDEX_ARGS=(
    --build-arg PYPI_URL="${PYPI_URL}"
    --build-arg PYPI_TRUSTED_HOST="$(python3 -c "from urllib.parse import urlsplit; print(urlsplit('${PYPI_URL}').hostname or 'pypi.org')")"
  )
fi

# ── W28C-1719 publish-before-pin guard + build-provenance revision label (fail-closed) ──
_PBP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
CANONICAL_SOURCE_FALLBACK_MANIFEST="${_PBP_DIR}/working/evidence/W28E-1889/current/package-source-fallback/package-source-fallback-manifest.tsv"
CANONICAL_SOURCE_FALLBACK_ARGS=()
if [[ -f "${CANONICAL_SOURCE_FALLBACK_MANIFEST}" ]]; then
  # The guard below validates the manifest, every wheel and every sdist before
  # the build may consume this narrowly-scoped fallback.  The Dockerfile uses
  # it only for the nine cloud-dog-* pins; all other dependencies keep the
  # existing single approved internal index.
  CANONICAL_SOURCE_FALLBACK_ARGS=(--build-arg CANONICAL_SOURCE_FALLBACK=1)
fi
# W28A-SEC-R18 public-boundary scrub: the publish-before-pin guard is internal-only
# tooling (hardcodes the internal package index host) and is excluded from the public
# mirror. On the public boundary it is absent; skip it when not present. Internal
# builds (guard present) keep the fail-closed behaviour unchanged.
if [[ -x "${_PBP_DIR}/scripts/publish-before-pin-guard.sh" ]]; then
  "${_PBP_DIR}/scripts/publish-before-pin-guard.sh" "${_PBP_DIR}" || exit $?
else
  echo "publish-before-pin guard absent (public boundary) — skipping."
fi
_PBP_REV="$(git -C "${_PBP_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
# W28E-1863 fix-wave-d (WSC-014): propagate build identity to the image so the
# Dockerfile can stamp OCI labels + runtime ENV for _build_identity() / /version.
SOURCE_COMMIT="${_PBP_REV}"
SOURCE_BRANCH="$(git -C "${_PBP_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# W28R-3017 Cloud-Dog-only boundary (AGENT-LESSONS §6.183 / W28R-3014 R4 accepted
# precedent): when REGISTRY is set for a non-publication build, tag the image
# directly with the internal registry ref so buildx never emits a
# `naming to docker.io/...` local-tag line in the build log (0x docker.io).
if [[ -n "${REGISTRY}" && -z "${PUBLICATION_TAG_SUFFIX}" ]]; then
  BUILD_TAG="${REGISTRY}/${FOLDER}/${CONTAINER}:${EFFECTIVE_TAG}"
else
  BUILD_TAG="${FOLDER}/${CONTAINER}:${EFFECTIVE_TAG}"
fi

# The wrapper must inspect and return the build child's exact status itself;
# temporarily disable errexit so pipefail cannot bypass cleanup and reporting.
set +e
docker buildx build \
  --label "org.opencontainers.image.revision=${_PBP_REV}" \
  --progress=plain \
  --network=host \
  --load \
  -f "${DOCKERFILE}" \
  --secret id=pip_conf,src="${PIP_CONF}" \
  "${PUBLIC_INDEX_ARGS[@]}" \
  "${CANONICAL_SOURCE_FALLBACK_ARGS[@]}" \
  --build-arg HTTP_PROXY="${HTTP_PROXY:-}" \
  --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
  --build-arg NO_PROXY="${NO_PROXY:-}" \
  --build-arg http_proxy="${http_proxy:-}" \
  --build-arg https_proxy="${https_proxy:-}" \
  --build-arg no_proxy="${no_proxy:-}" \
  --build-arg SOURCE_COMMIT="${SOURCE_COMMIT}" \
  --build-arg SOURCE_BRANCH="${SOURCE_BRANCH}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  -t "${BUILD_TAG}" \
  . 2>&1 | tee "${LOG_FILE}"

BUILD_STATUS=${PIPESTATUS[0]}
set -e

if [ ${BUILD_STATUS} -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Build completed successfully!"
    echo "=========================================="
    echo ""
    echo "Built image:"
    docker images | grep "${CONTAINER}" || true
    echo ""
    if [[ -n "${REGISTRY}" && -z "${PUBLICATION_TAG_SUFFIX}" ]]; then
        echo "Image tagged registry-direct as ${BUILD_TAG} (W28R-3017 Cloud-Dog-only boundary)."
        echo "To push: docker push ${BUILD_TAG}"
    elif [[ -n "${PUBLICATION_TAG_SUFFIX}" ]]; then
        echo "Publication test image (suffix=${PUBLICATION_TAG_SUFFIX}); internal registry tag intentionally skipped (W28A-831 isolation)."
    else
        echo "Registry tag skipped; set REGISTRY to tag a registry image."
    fi
else
    echo ""
    echo "=========================================="
    echo "✗ Build failed!"
    echo "=========================================="
    echo ""
    echo "Build log saved to: ${LOG_FILE}"
fi

if [ ${BUILD_STATUS} -ne 0 ]; then
    exit "${BUILD_STATUS}"
fi
