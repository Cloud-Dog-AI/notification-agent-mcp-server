# Slow Integration Tests

Network-backed integration tests that require `server_control.sh` remain in the
existing `tests/integration/IT*` directories. New or migrated in-process
integration checks should live under `tests/integration/fast`.
