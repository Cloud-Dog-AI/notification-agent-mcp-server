---
template-id: T-EXT
template-version: 1.0
applies-to: EXTERNAL-BUILD.md
registry: service
required: must-have
when-applicable: ""
template-last-updated: 2026-06-12
template-owner: platform-standards

project: notification-agent-mcp-server
doc-last-updated: 2026-06-18
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: 90d
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# External Build Guide — notification-agent-mcp-server

Self-contained instructions for an **external builder** (no access to any internal
Cloud-Dog network, Vault, or private registry) to build, run, and smoke-test this
service from a public clone, then return evidence.

This document assumes only public resources: a public Git host, public PyPI
(`https://pypi.org/simple`), and a public container registry. It never reaches an
internal Cloud-Dog host.

---

## 1. Prerequisites

| Tool        | Minimum | Notes |
|-------------|---------|-------|
| Docker      | 24+     | BuildKit enabled (default in 24+). Required for the container path. |
| Python      | 3.12+   | Required for the pure-source path and `py_compile` checks. |
| Git         | 2.30+   | To clone the public repository. |
| curl        | any     | Used by the smoke probes. |

Platform notes:

- **Linux:** all commands below run as-is in `bash`.
- **macOS:** install Docker Desktop and the Xcode command-line tools (`xcode-select
  --install`). The native PDF libraries (cairo/pango) are bundled in the Docker
  image, so the **container path is recommended** on macOS.
- **Windows:** use **WSL2** (Ubuntu) with Docker Desktop's WSL2 backend, then follow
  the Linux commands inside the WSL2 shell. PowerShell-native builds are not
  supported because the service relies on POSIX `server_control.sh`.

---

## 2. Clone (public boundary)

```bash
git clone https://github.com/cloud-dog-ai/notification-agent-mcp-server.git
cd notification-agent-mcp-server

# Verify the clone is boundary-clean (no internal remotes):
git remote -v        # must show ONLY the public remote, zero internal/gitlab URLs
```

---

## 3. Package source strategy (public boundary)

Per the platform isolation standard (PS-97 §3.3 / §4):

- **Single index only.** All dependencies — including the Cloud-Dog platform
  packages — resolve from **one** public index passed via `PIP_INDEX_URL`
  (default `https://pypi.org/simple`). **No `--extra-index-url`** is used anywhere.
- Cloud-Dog platform packages (`cloud-dog-config`, `cloud-dog-logging`,
  `cloud-dog-api-kit`, `cloud-dog-idam`, `cloud-dog-db`, `cloud-dog-jobs`,
  `cloud-dog-llm`, `cloud-dog-cache`, `cloud-dog-storage`) must be present on that
  index (e.g. pypi.org under the `Cloud-Dog-External` namespace) or installed from
  their GitHub-mirrored source. If a platform package is missing, **stop and report
  the gap** — do not add a second index to work around it.

---

## 4. Build — Docker path (recommended)

```bash
# Public variant; default index = pypi.org. Override PIP_INDEX_URL only with
# another PUBLIC index (e.g. GitHub Packages).
./docker-build.sh --variant public latest

# Or explicitly:
PYPI_URL=https://pypi.org/simple ./docker-build.sh --variant public latest
```

This builds `cloud-dog/notification-agent-mcp-server:latest` from `Dockerfile.public`.
The build uses a single `--index-url`; it does not COPY vendored wheels and does not
install an internal CA.

Behind a corporate proxy, export `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` first.

---

## 5. Build — pure-source path (no Docker)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip setuptools wheel

# Single public index only:
pip install --index-url https://pypi.org/simple -e .
```

The PDF channel (weasyprint) needs the native cairo/pango libraries on the host. On
Debian/Ubuntu:

```bash
sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu-core
```

---

## 6. Run + smoke test

Use the checked-in public env example and the probe block in
[`PUBLICATION-SMOKE.md`](PUBLICATION-SMOKE.md):

```bash
# Container path:
docker run -d --name na-smoke --network host \
  -v "$PWD/docker-env.public.example:/app/env:ro" \
  cloud-dog/notification-agent-mcp-server:latest

# Then probe (see PUBLICATION-SMOKE.md for the full block):
curl -fsS http://127.0.0.1:8083/health   # API
curl -fsS http://127.0.0.1:8080/         # Web UI
curl -fsS http://127.0.0.1:8081/health   # MCP
curl -fsS http://127.0.0.1:8082/health   # A2A
curl -fsS http://127.0.0.1:8082/.well-known/agent.json
```

Default public ports: **API 8083, Web 8080, MCP 8081, A2A 8082**. Auth-gated
`401/403` or `2xx/3xx` responses count as PASS — they prove the surface is routing.

---

## 7. Return evidence

Collect into a directory named `external-build-evidence/`:

1. `git-remote.txt` — output of `git remote -v` (proves boundary-clean clone).
2. `docker-build.log` — produced by `docker-build.sh` in the repo root.
3. `image-digest.txt` — `docker inspect --format '{{.Id}}' cloud-dog/notification-agent-mcp-server:latest`.
4. `smoke.txt` — the full output of the smoke probe block (all PASS lines).
5. `pip-index.txt` — grep proving a single index: `grep -E 'index-url' docker-build.log`.

Then create a tarball and checksum:

```bash
tar czf external-build-evidence.tar.gz external-build-evidence/
sha256sum external-build-evidence.tar.gz > external-build-evidence.sha256
```

Return both `external-build-evidence.tar.gz` and `external-build-evidence.sha256` to
the coordinator. Do **not** include any `.env`, secret, or credential file in the
tarball.
