#!/usr/bin/env python3
"""
Start script for MCP Server
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

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
    from src.config import get_config
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start Notification Agent MCP Server")
    parser.add_argument(
        "--env",
        type=str,
        help="Path to environment file (e.g., private/env-test)"
    )
    args = parser.parse_args()
    
    if not args.env:
        print("❌ CRITICAL: --env flag is required (e.g., --env private/env-test)", file=sys.stderr)
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

    env_path = str(args.env or "")
    is_test_env = env_path.startswith("tests/") or "/tests/" in env_path
    if not is_test_env:
        config.validate_startup_requirements()

    transport = config.get("mcp_server.transport")
    if not transport:
        raise RuntimeError("Missing required configuration: mcp_server.transport")
    transport = transport.lower()
    
    # Keep stdout clean for stdio transport (JSON-RPC frames only).
    print("Starting MCP server...", file=sys.stderr)
    print(f"Transport: {transport}", file=sys.stderr)
    print(
        "Tools: send_notification, send_notification_natural, get_message_status, list_channels, "
        "cancel_message, list_messages, get_message, list_deliveries, resend_delivery, abort_delivery, get_status",
        file=sys.stderr,
    )
    
    if transport in ("sse", "http", "legacy_sse"):
        # Use HTTP/SSE transport (blocking, no asyncio.run needed)
        from src.servers.mcp.mcp_server_http import MCPServerHTTP
        http_server = MCPServerHTTP(config=config)
        http_server.run()
    elif transport in ("streamable_http", "http_jsonrpc", "http_jsonrpc_async"):
        from src.servers.mcp.mcp_server_http import MCPServerJSONRPC
        jsonrpc_server = MCPServerJSONRPC(config=config, transport_mode=transport)
        jsonrpc_server.run()
    else:
        # Use stdio transport (async)
        from src.servers.mcp.mcp_server import main as mcp_main
        asyncio.run(mcp_main())


if __name__ == "__main__":
    main()

