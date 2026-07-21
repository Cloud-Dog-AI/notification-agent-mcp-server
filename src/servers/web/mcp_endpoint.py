"""Pure URL helpers for the authenticated MCP web proxy."""

from urllib.parse import urlsplit


def mcp_endpoint(base_url: str, jsonrpc_path: str) -> str:
    """Join an MCP base URL and JSON-RPC path without duplicating its mount."""
    base = base_url.rstrip("/")
    path = f"/{jsonrpc_path.lstrip('/')}"
    base_path = urlsplit(base).path.rstrip("/")
    if base_path and (path == base_path or path.startswith(f"{base_path}/")):
        origin = base[: -len(base_path)]
        return f"{origin}{path}"
    return f"{base}{path}"
