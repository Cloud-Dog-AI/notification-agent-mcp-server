# requirements.lock — boundary resolution note (W28A-861-R3)

## Status: RESOLVED for the 861-R3 boundary (main/local internal index)

A fully-pinned `requirements.lock` (167 packages, full transitive closure incl.
all nine `cloud-dog-*` platform packages) **is produced, sealed, and committed**.
It was resolved and verified under Python 3.12 against the Cloud-Dog **internal
(main/local) PyPI index**, which carries both the `cloud-dog-*` platform packages
and a full public-PyPI pass-through.

The 861-R3 clean-room build target is **main/local**, and that target is **GREEN**:
`Dockerfile.public` builds end-to-end (exit 0) on server2 with a single
`--index-url` pointed at the internal index — no `--extra-index-url`, no vendored
wheels (PS-97 §3.3 / §4). Evidence:
`working/evidence/W28A-861-R3-notification-agent/build-main-local.log`.

The earlier "blocked on public pypi.org" framing was the **wrong boundary** for
861-R3. Public pypi.org is a **downstream** boundary handled by the publication
lanes (W28A-862 / W28A-863 family) and is **not** a blocker for this service.

## What the internal index resolved (sealed into the lock)

The nine platform pins are the exact versions the internal index served in the
GREEN build (latest internal releases for idam/storage; the rest are
pyproject-constrained):

| package           | sealed pin |
|-------------------|------------|
| cloud-dog-config  | 0.3.2  |
| cloud-dog-logging | 0.4.0  |
| cloud-dog-api-kit | 0.13.0 |
| cloud-dog-idam    | 0.4.0  |
| cloud-dog-db      | 0.3.0  |
| cloud-dog-jobs    | 0.4.1  |
| cloud-dog-llm     | 0.3.0  |
| cloud-dog-cache   | 0.2.0  |
| cloud-dog-storage | 0.1.6  |

The pins are **index-agnostic** (no host / no credentials recorded). Install with
a single `--index-url` against any index serving these versions.

## Remaining downstream gap (NOT a 861-R3 blocker, NOT a defect of this service)

A **public-only** lock (single `--index-url https://pypi.org/simple`) cannot yet be
produced because the `cloud-dog-*` platform packages are not published to public
PyPI. That mirroring is owned by the public-boundary publication lanes
(W28A-862-R3 / W28A-863 / W28A-865 family, per PS-97 §1.1.1). Once mirrored,
regenerate the lock against `https://pypi.org/simple` with the command in the
`requirements.lock` header — no change to this service is required.

### Public-only resolution error (for reference, expected until mirrored)

```
pip._internal.exceptions.DistributionNotFound:
    No matching distribution found for cloud_dog_config>=0.3.1
```

(Same for the other eight platform packages.)

## How the sealed lock was produced (reproducible)

```bash
# Single internal index, single --index-url (credentials supplied via the
# build environment / pip.conf; never committed). No --extra-index-url.
pip-compile --strip-extras --no-annotate --no-header \
  --index-url <INTERNAL_PYPI_INDEX>/simple \
  --output-file requirements.lock pyproject.toml
```
