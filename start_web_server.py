#!/usr/bin/env python3
"""
Start script for Web UI Server
"""

import sys
import argparse
import uvicorn
import os
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start Notification Agent Web UI Server")
    parser.add_argument(
        "--env",
        type=str,
        help="Path to environment file (e.g., private/env-test)"
    )
    args = parser.parse_args()
    
    if not args.env:
        print("❌ CRITICAL: --env flag is required (e.g., --env private/env-test)")
        sys.exit(1)
    
    # Load configuration using the required env file
    config = get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        env_file=args.env,
        load_env_file=True,
        force_reload=True,
        unresolved_policy="empty",
    )

    resolved_api_key = str(
        config.get("api_server.api_key")
        or config.get("runtime.a2a_test_api_key")
        or "st-local-secret"
    )
    resolved_username = str(config.get("web_server.username") or "")
    resolved_password = str(config.get("web_server.password") or "").strip() or "st-local-secret"
    resolved_jwt_secret = str(config.get("auth.jwt_secret") or "").strip() or "st-web-session-secret"
    resolved_env = {
        "CLOUD_DOG__APP__ENV_FILE": args.env,
        "CLOUD_DOG__API_SERVER__API_KEY": resolved_api_key,
        "CLOUD_DOG__WEB_SERVER__USERNAME": resolved_username,
        "CLOUD_DOG__WEB_SERVER__PASSWORD": resolved_password,
        "CLOUD_DOG__AUTH__JWT_SECRET": resolved_jwt_secret,
        "CLOUD_DOG__NOTIFY__APP__ENV_FILE": args.env,
        "CLOUD_DOG__NOTIFY__API_SERVER__API_KEY": resolved_api_key,
        "CLOUD_DOG__NOTIFY__WEB_SERVER__USERNAME": resolved_username,
        "CLOUD_DOG__NOTIFY__WEB_SERVER__PASSWORD": resolved_password,
        "CLOUD_DOG__NOTIFY__AUTH__JWT_SECRET": resolved_jwt_secret,
    }
    for key, value in resolved_env.items():
        if value:
            os.environ[key] = value

    # Get server settings
    host = config.get("web_server.host")
    port = config.get("web_server.port")
    log_level = config.get("log.level")
    if not host:
        raise RuntimeError("Missing required configuration: web_server.host")
    if port is None or port == "":
        raise RuntimeError("Missing required configuration: web_server.port")
    if not log_level:
        raise RuntimeError("Missing required configuration: log.level")
    log_level = log_level.lower()
    
    print(f"Starting Web UI server on {host}:{port}")
    print(f"Dashboard: http://{host}:{port}/dashboard")
    print("Credentials are configured via env/config")
    
    # Run server
    uvicorn.run(
        "src.servers.web.web_server:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
