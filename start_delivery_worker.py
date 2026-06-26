#!/usr/bin/env python3
"""
Start script for Delivery Worker Server
"""

import sys
import argparse
import os
from pathlib import Path

import uvicorn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config

# W28A-654: Patch cloud_dog_logging ContextVar defaults at module import time.
# ContextVars are task-scoped in asyncio — set_environment() in one task does NOT
# propagate to AuditMiddleware in another. Patching defaults ensures all tasks inherit.
try:
    import contextvars as _ctxvars, os as _patch_os
    from cloud_dog_logging import correlation as _cmod
    _cmod._environment_var = _ctxvars.ContextVar(
        "environment", default=_patch_os.environ.get("CLOUD_DOG_ENVIRONMENT", "dev"))
    _cmod._service_name_var = _ctxvars.ContextVar(
        "service_name", default="notification-agent-mcp-server")
    _cmod._service_instance_var = _ctxvars.ContextVar(
        "service_instance", default=_patch_os.environ.get("HOSTNAME", "notification-agent-local"))
    del _ctxvars, _patch_os, _cmod
except Exception:
    pass  # cloud_dog_logging not installed or incompatible version


def _config_truthy(value, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Start Notification Agent Delivery Worker")
    parser.add_argument(
        "--env",
        type=str,
        help="Path to environment file (e.g., private/env-test)",
    )
    args = parser.parse_args()

    if not args.env:
        print("❌ CRITICAL: --env flag is required (e.g., --env private/env-test)")
        sys.exit(1)

    config = get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        env_file=args.env,
        load_env_file=True,
        force_reload=True,
        unresolved_policy="empty",
    )

    resolved_env = {
        "CLOUD_DOG__APP__ENV_FILE": args.env,
        "CLOUD_DOG__NOTIFY__APP__ENV_FILE": args.env,
    }
    for key, value in resolved_env.items():
        if value:
            os.environ[key] = value

    env_path = str(config.get("app.env_file") or args.env).replace("\\", "/").lower()
    is_test_env = env_path.startswith("tests/") or "/tests/" in env_path
    if not is_test_env:
        config.validate_startup_requirements()

    if not _config_truthy(config.get("delivery_worker.enabled", True), True):
        raise RuntimeError("delivery_worker.enabled is false")

    host = config.get("delivery_worker.host")
    port = config.get("delivery_worker.port")
    log_level = config.get("log.level")
    if not host:
        raise RuntimeError("Missing required configuration: delivery_worker.host")
    if port is None or port == "":
        raise RuntimeError("Missing required configuration: delivery_worker.port")
    if not log_level:
        raise RuntimeError("Missing required configuration: log.level")
    log_level = str(log_level).lower()

    display_host = "127.0.0.1" if str(host).strip() in {"0.0.0.0", "::"} else str(host).strip()

    print(f"Starting delivery worker on {host}:{port}")
    print(f"Worker health: http://{display_host}:{port}/worker/health")

    uvicorn.run(
        "src.servers.worker.worker_server:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
