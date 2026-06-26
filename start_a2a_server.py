#!/usr/bin/env python3
"""
Start script for A2A Server
"""

import sys
import argparse
import uvicorn
from pathlib import Path

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



def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Start Notification Agent A2A Server")
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

    env_path = str(args.env or "")
    is_test_env = env_path.startswith("tests/") or "/tests/" in env_path
    if not is_test_env:
        config.validate_startup_requirements()

    host = config.get("a2a_server.host")
    port = config.get("a2a_server.port")
    log_level = config.get("log.level")
    if not host:
        raise RuntimeError("Missing required configuration: a2a_server.host")
    if port is None or port == "":
        raise RuntimeError("Missing required configuration: a2a_server.port")
    if not log_level:
        raise RuntimeError("Missing required configuration: log.level")
    log_level = str(log_level).lower()

    print(f"Starting A2A server on {host}:{port}")
    print(f"WebSocket endpoint: ws://{host}:{port}/stream")
    print("Topics: notifications.events, deliveries.{id}, channels.state")

    uvicorn.run(
        "src.servers.a2a.a2a_server:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
