#!/usr/bin/env python3
"""APIRouter routes extracted from web_server.py: runtime static handlers and legacy page views."""

from fastapi import APIRouter
from . import web_server as _web

globals().update({name: value for name, value in vars(_web).items() if not name.startswith("__")})
router = APIRouter()

@router.get("/runtime-config.js", response_class=Response)
async def runtime_config_js(request: Request) -> Response:
    payload = _runtime_config_payload(request)
    mcp_base_path = _configured_base_path("mcp_server.base_path", default="/mcp")
    a2a_base_path = _configured_base_path("a2a_server.base_path", default="/a2a")
    runtime = {
        "ENV": payload.get("ENV", "dev"),
        "API_BASE_URL": "",
        "MCP_BASE_URL": "",
        "A2A_BASE_URL": "",
        "AUTH_MODE": payload.get("AUTH_MODE", "cookie"),
        "SESSION_TIMEOUT_MINUTES": payload.get("SESSION_TIMEOUT_MINUTES", 30),
    }
    for key in ("IDP_AUTHORITY", "IDP_CLIENT_ID", "IDP_REDIRECT_URI", "IDP_SCOPES"):
        if key in payload:
            runtime[key] = payload[key]
    body = "\n".join([
        "const __origin = window.location.origin;",
        f"window.__RUNTIME_CONFIG__ = {json.dumps(runtime)};",
        'window.__RUNTIME_CONFIG__["API_BASE_URL"] = __origin;',
        f'window.__RUNTIME_CONFIG__["MCP_BASE_URL"] = __origin + {json.dumps(mcp_base_path)};',
        f'window.__RUNTIME_CONFIG__["A2A_BASE_URL"] = __origin + {json.dumps(a2a_base_path)};',
        "",
    ])
    return Response(
        content=body,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


# Root - redirect to dashboard or login

async def root(request: Request):
    """Root endpoint - redirect based on auth status"""
    user = request.session.get("user")
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


# Login page with branding

def get_base_layout(title: str, active_page: str = "dashboard", content: str = "", user: str = "admin"):
    """
    Generate base HTML layout with left sidebar menu

    Args:
        title: Page title
        active_page: Active page identifier for menu highlighting
        content: Main content HTML
        user: Current username
    """
    # Get user permissions for menu items
    # For now, show all items - RBAC will filter later

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Notification Agent</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --primary: #667eea;
            --primary-dark: #5568d3;
            --secondary: #764ba2;
            --accent: #f093fb;
            --success: #4CAF50;
            --warning: #ff9800;
            --danger: #f44336;
            --info: #2196F3;
            --bg-primary: #0f0f1e;
            --bg-secondary: #1a1a2e;
            --bg-tertiary: #16213e;
            --text-primary: #e0e0e0;
            --text-secondary: #a0a0a0;
            --border: #333;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .app-wrapper {{
            display: flex;
            flex: 1;
        }}
        /* Sidebar Navigation */
        .sidebar {{
            width: 250px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }}
        .sidebar-header {{
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }}
        .sidebar-header h2 {{
            font-size: 18px;
            margin-bottom: 5px;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .sidebar-header p {{
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .nav-section {{
            padding: 15px 0;
            border-bottom: 1px solid var(--border);
        }}
        .nav-section:last-child {{
            border-bottom: none;
        }}
        .nav-section-title {{
            padding: 0 20px 10px;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-secondary);
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .nav-item {{
            padding: 12px 20px;
            cursor: pointer;
            transition: all 0.3s;
            border-left: 3px solid transparent;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            text-decoration: none;
            color: var(--text-primary);
        }}
        .nav-item:hover {{
            background: var(--bg-tertiary);
            border-left-color: var(--primary);
        }}
        .nav-item.active {{
            background: rgba(102, 126, 234, 0.1);
            border-left-color: var(--primary);
            color: var(--primary);
            font-weight: 600;
        }}
        .nav-icon {{
            font-size: 16px;
            min-width: 20px;
        }}
        /* Main Content */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
        }}
        .header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-title {{
            font-size: 24px;
            font-weight: 600;
        }}
        .header-actions {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}
        .user-info {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            color: var(--text-secondary);
        }}
        .content-area {{
            flex: 1;
            overflow-y: auto;
            padding: 30px;
        }}
        /* Cards and Components */
        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s;
        }}
        .card:hover {{
            border-color: var(--primary);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.1);
        }}
        .card-title {{
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        /* Buttons */
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }}
        .btn-secondary {{
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }}
        .btn-danger {{
            background: var(--danger);
            color: white;
        }}
        .btn-success {{
            background: var(--success);
            color: white;
        }}
        .btn-small {{
            padding: 6px 12px;
            font-size: 12px;
        }}
        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-secondary);
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            background: var(--bg-tertiary);
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-secondary);
        }}
        td {{
            padding: 12px;
            border-top: 1px solid var(--border);
        }}
        tr:hover {{
            background: var(--bg-tertiary);
        }}
    </style>
</head>
<body>
    <div class="app-wrapper">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h2>🔔 Notification Agent</h2>
                <p id="serverStatus">● Ready</p>
            </div>

            <div class="nav-section">
                <div class="nav-section-title">Dashboard</div>
                <a href="/dashboard" class="nav-item {'active' if active_page == 'dashboard' else ''}">
                    <span class="nav-icon">📊</span>
                    <span>Dashboard</span>
                </a>
            </div>

            <div class="nav-section">
                <div class="nav-section-title">Management</div>
                <a href="/users" class="nav-item {'active' if active_page == 'users' else ''}">
                    <span class="nav-icon">👥</span>
                    <span>Users</span>
                </a>
                <a href="/admin/api-keys" class="nav-item {'active' if active_page == 'api-keys' else ''}">
                    <span class="nav-icon">🔑</span>
                    <span>API Keys</span>
                </a>
                <a href="/groups" class="nav-item {'active' if active_page == 'groups' else ''}">
                    <span class="nav-icon">👤</span>
                    <span>Groups</span>
                </a>
                <a href="/channels" class="nav-item {'active' if active_page == 'channels' else ''}">
                    <span class="nav-icon">📡</span>
                    <span>Channels</span>
                </a>
            </div>

            <div class="nav-section">
                <div class="nav-section-title">Messages</div>
                <a href="/messages" class="nav-item {'active' if active_page == 'messages' else ''}">
                    <span class="nav-icon">💬</span>
                    <span>Messages</span>
                </a>
                <a href="/deliveries" class="nav-item {'active' if active_page == 'deliveries' else ''}">
                    <span class="nav-icon">📦</span>
                    <span>Deliveries</span>
                </a>
            </div>

            <div class="nav-section">
                <div class="nav-section-title">System</div>
                <a href="/services" class="nav-item {'active' if active_page == 'services' else ''}">
                    <span class="nav-icon">⚙️</span>
                    <span>Services</span>
                </a>
                <a href="/status" class="nav-item {'active' if active_page == 'status' else ''}">
                    <span class="nav-icon">🎯</span>
                    <span>Status</span>
                </a>
                <a href="/logs" class="nav-item {'active' if active_page == 'logs' else ''}">
                    <span class="nav-icon">📋</span>
                    <span>Logs</span>
                </a>
                <a href="/mcp-logs" class="nav-item {'active' if active_page == 'mcp-logs' else ''}">
                    <span class="nav-icon">🔌</span>
                    <span>MCP Logs</span>
                </a>
                <a href="/storage" class="nav-item {'active' if active_page == 'storage' else ''}">
                    <span class="nav-icon">💾</span>
                    <span>Storage</span>
                </a>
            </div>

            <div class="nav-section">
                <div class="nav-section-title">Testing</div>
                <a href="/web-mcp-test" class="nav-item {'active' if active_page == 'mcp-test' else ''}">
                    <span class="nav-icon">🔧</span>
                    <span>MCP/A2A Test</span>
                </a>
                <a href="/llm-test" class="nav-item {'active' if active_page == 'llm-test' else ''}">
                    <span class="nav-icon">🤖</span>
                    <span>LLM Test</span>
                </a>
            </div>

            <div class="nav-section">
                <div class="nav-section-title">Settings</div>
                <a href="/settings" class="nav-item {'active' if active_page == 'settings' else ''}">
                    <span class="nav-icon">⚙️</span>
                    <span>Configuration</span>
                </a>
                <a href="/web-api-docs" class="nav-item {'active' if active_page == 'api-docs' else ''}">
                    <span class="nav-icon">📚</span>
                    <span>API Documentation</span>
                </a>
            </div>

            <div class="nav-section" style="margin-top: auto;">
                <a href="/logout" class="nav-item btn-danger btn-small" style="width: calc(100% - 40px); margin: 10px 20px; text-align: center;">
                    🚪 Logout
                </a>
            </div>
        </div>

        <!-- Main Content Area -->
        <div class="main-content">
            <div class="header">
                <h1 class="header-title">{title}</h1>
                <div class="header-actions">
                    <div class="user-info">
                        <span>👤 {user}</span>
                    </div>
                </div>
            </div>

            <div class="content-area">
                {content}
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html


# API Proxy endpoints for client-side JavaScript

async def view_status(request: Request, user: str = Depends(get_current_user)):
    """Comprehensive status page showing all servers and current activity"""
    return _ui_index_response()
    # psutil is optional; module-level import may set it to None

    # Get service statuses
    api_port = _require_config(config.get("api_server.port"), "api_server.port")
    web_port = _require_config(config.get("web_server.port"), "web_server.port")
    a2a_port = _require_config(config.get("a2a_server.port"), "a2a_server.port")
    web_base_url = _require_config(config.get("web_server.base_url"), "web_server.base_url")
    a2a_base_url = _require_config(config.get("a2a_server.base_url"), "a2a_server.base_url")

    api_health = {"status": "unknown", "port": api_port}
    web_health = {"status": "unknown", "port": web_port}
    a2a_health = {"status": "unknown", "port": a2a_port}

    # Get process info
    api_process = None
    web_process = None
    a2a_process = None

    health_client = _get_internal_client()
    try:
        api_response = await health_client.get(f"{api_base_url}/health")
        api_health = api_response.json() if api_response.status_code == 200 else {"status": "unhealthy", "port": api_port}
        api_health["port"] = api_port
    except Exception:
        api_health = {"status": "unavailable", "port": api_port}

    try:
        web_response = await health_client.get(f"{web_base_url}/health")
        web_health = web_response.json() if web_response.status_code == 200 else {"status": "unhealthy", "port": web_port}
        web_health["port"] = web_port
    except Exception:
        web_health = {"status": "unavailable", "port": web_port}

    try:
        a2a_response = await health_client.get(f"{a2a_base_url}/health")
        a2a_health = a2a_response.json() if a2a_response.status_code == 200 else {"status": "unhealthy", "port": a2a_port}
        a2a_health["port"] = a2a_port
    except Exception:
        a2a_health = {"status": "unavailable", "port": a2a_port}

    # Try to get process info (if psutil is available)
    if psutil:
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'num_threads', 'connections']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    proc_info = proc.info.copy()
                    # Convert memory_info pmem object to dict for easier access
                    if proc_info.get('memory_info'):
                        mem_info = proc_info['memory_info']
                        proc_info['memory_info'] = {'rss': mem_info.rss, 'vms': mem_info.vms}
                    if 'api_server' in cmdline or '8004' in cmdline:
                        api_process = proc_info
                    elif 'web_server' in cmdline or '8005' in cmdline:
                        web_process = proc_info
                    elif 'a2a_server' in cmdline or str(a2a_health["port"]) in cmdline:
                        a2a_process = proc_info
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

    # Get database stats (gracefully handle API unavailability)
    db_stats = {"messages": 0, "deliveries": 0, "users": 0, "groups": 0, "channels": 0}
    try:
        result = await api_request("GET", _api_target_path("/messages"), params={"limit": 1})
        db_stats["messages"] = result.get("total", 0)
    except Exception:
        pass
    try:
        result = await api_request("GET", _api_target_path("/deliveries"), params={"limit": 1})
        db_stats["deliveries"] = result.get("total", 0)
    except Exception:
        pass
    try:
        result = await api_request("GET", _api_target_path("/users"), params={"limit": 1})
        db_stats["users"] = result.get("total", 0)
    except Exception:
        pass
    try:
        result = await api_request("GET", _api_target_path("/groups"), params={"limit": 1})
        db_stats["groups"] = result.get("total", 0)
    except Exception:
        pass
    try:
        result = await api_request("GET", _api_target_path("/channels"), params={"limit": 1})
        db_stats["channels"] = result.get("total", 0)
    except Exception:
        pass

    def format_bytes(bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} TB"

    content = f"""
    <style>
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .status-card {{
            padding: 20px;
        }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }}
        .stat-label {{
            color: var(--text-secondary);
        }}
        .stat-value {{
            font-weight: 600;
        }}
        .activity-section {{
            margin-top: 20px;
        }}
    </style>

    <div class="status-grid">
        <div class="card status-card">
            <h3 class="card-title">API Server</h3>
            <div class="stat-row">
                <span class="stat-label">Status:</span>
                <span class="stat-value status {'status-sent' if api_health.get('status') == 'healthy' else 'status-failed'}">
                    {api_health.get('status', 'unknown').upper()}
                </span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Port:</span>
                <span class="stat-value">{api_health.get('port', 8004)}</span>
            </div>
            {f'''
            <div class="stat-row">
                <span class="stat-label">PID:</span>
                <span class="stat-value">{api_process.get("pid", "N/A")}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Threads:</span>
                <span class="stat-value">{api_process.get("num_threads", "N/A")}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">CPU:</span>
                <span class="stat-value">{api_process.get("cpu_percent", 0):.1f}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Memory:</span>
                <span class="stat-value">{format_bytes(api_process.get("memory_info", {}).get("rss", 0))}</span>
            </div>
            ''' if api_process else '<div class="stat-row"><span class="stat-label">Process:</span><span class="stat-value">Not found</span></div>'}
        </div>

        <div class="card status-card">
            <h3 class="card-title">Web UI Server</h3>
            <div class="stat-row">
                <span class="stat-label">Status:</span>
                <span class="stat-value status {'status-sent' if web_health.get('status') == 'healthy' else 'status-failed'}">
                    {web_health.get('status', 'unknown').upper()}
                </span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Port:</span>
                <span class="stat-value">{web_health.get('port', 8005)}</span>
            </div>
            {f'''
            <div class="stat-row">
                <span class="stat-label">PID:</span>
                <span class="stat-value">{web_process.get("pid", "N/A")}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Threads:</span>
                <span class="stat-value">{web_process.get("num_threads", "N/A")}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">CPU:</span>
                <span class="stat-value">{web_process.get("cpu_percent", 0):.1f}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Memory:</span>
                <span class="stat-value">{format_bytes(web_process.get("memory_info", {}).get("rss", 0))}</span>
            </div>
            ''' if web_process else '<div class="stat-row"><span class="stat-label">Process:</span><span class="stat-value">Not found</span></div>'}
        </div>

        <div class="card status-card">
            <h3 class="card-title">A2A Server</h3>
            <div class="stat-row">
                <span class="stat-label">Status:</span>
                <span class="stat-value status {'status-sent' if a2a_health.get('status') == 'healthy' else 'status-failed'}">
                    {a2a_health.get('status', 'unknown').upper()}
                </span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Port:</span>
                <span class="stat-value">{a2a_health.get('port', 8082)}</span>
            </div>
            {f'''
            <div class="stat-row">
                <span class="stat-label">PID:</span>
                <span class="stat-value">{a2a_process.get("pid", "N/A")}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Threads:</span>
                <span class="stat-value">{a2a_process.get("num_threads", "N/A")}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">CPU:</span>
                <span class="stat-value">{a2a_process.get("cpu_percent", 0):.1f}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Memory:</span>
                <span class="stat-value">{format_bytes(a2a_process.get("memory_info", {}).get("rss", 0))}</span>
            </div>
            ''' if a2a_process else '<div class="stat-row"><span class="stat-label">Process:</span><span class="stat-value">Not found</span></div>'}
        </div>
    </div>

    <div class="card activity-section">
        <h3 class="card-title">Database Statistics</h3>
        <div class="stat-row">
            <span class="stat-label">Messages:</span>
            <span class="stat-value">{db_stats.get('messages', 0)}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Deliveries:</span>
            <span class="stat-value">{db_stats.get('deliveries', 0)}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Users:</span>
            <span class="stat-value">{db_stats.get('users', 0)}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Groups:</span>
            <span class="stat-value">{db_stats.get('groups', 0)}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Channels:</span>
            <span class="stat-value">{db_stats.get('channels', 0)}</span>
        </div>
    </div>

    <script>
        // Auto-refresh every 10 seconds
        setInterval(() => location.reload(), 10000);
    </script>
"""
    html = get_base_layout("System Status", "status", content, user)
    return HTMLResponse(content=html)


# Storage page - Access storage, link storage->delivery->message

async def view_storage(request: Request, user: str = Depends(get_current_user)):
    """Storage management page with links to deliveries and messages"""
    return _ui_index_response()
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent
    # Get database file info - use relative path
    db_uri = _require_config(config.get("db.uri"), "db.uri")
    # Extract path from sqlite3:/// URI
    if db_uri.startswith("sqlite3:///"):
        db_path_str = db_uri.replace("sqlite3:///", "")
        # Convert absolute path to relative if it's in the project directory
        try:
            db_path_abs = Path(db_path_str)
            if db_path_abs.is_absolute():
                # Try to make it relative to project root
                try:
                    db_path = db_path_abs.relative_to(project_root)
                except ValueError:
                    # If not in project root, use absolute but display as relative-looking
                    db_path = db_path_abs
            else:
                db_path = Path(db_path_str)
        except Exception:
            db_path = Path(db_path_str)
    else:
        db_path = Path("database/notify.db")

    db_size = 0
    db_path_abs = db_path if db_path.is_absolute() else project_root / db_path
    _db_stat = _fs.stat(str(db_path_abs))
    if _db_stat is not None:
        db_size = _db_stat.size

    # Get message storage statistics
    from ...database.db_manager import get_db_manager
    from ...database.repositories import MessageRepository, DeliveryRepository
    db = get_db_manager(db_uri)
    message_repo = MessageRepository(db)
    DeliveryRepository(db)

    # Get message statistics
    total_messages = await asyncio.get_event_loop().run_in_executor(
        None, message_repo.count
    )

    # Get delivery statistics
    delivery_stats = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: db.fetchone("SELECT COUNT(*) as count FROM deliveries")
    )
    total_deliveries = delivery_stats.get("count", 0) if delivery_stats else 0

    # Estimate message storage size (rough estimate: average message size)
    # This is approximate - actual storage is in database
    estimated_message_storage = total_messages * 1024  # Assume ~1KB per message on average

    # Get log directory info - get ALL files, not just .log
    import os as _os_mod
    log_dir_str = str(Path(config.get("log.directory", "./logs")))
    log_files = []
    total_log_size = 0
    if _fs.exists(log_dir_str):
        # Get all files in log directory (not just .log)
        for entry in _fs.list_dir(log_dir_str):
            if not entry.is_dir:
                try:
                    entry_stat = _fs.stat(entry.path)
                    size = entry_stat.size if entry_stat else 0
                    total_log_size += size
                    log_files.append({
                        "name": _os_mod.path.basename(entry.path),
                        "size": size,
                        "modified": datetime.fromtimestamp(_os_mod.path.getmtime(entry.path)).isoformat() if entry_stat else "",
                    })
                except Exception:
                    # Skip files we can't access
                    pass

    def format_bytes(bytes_val):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} TB"

    # Build log files table HTML separately to avoid nested f-string issues
    log_table_html = ""
    if log_files:
        table_rows = []
        for log_file in sorted(log_files, key=lambda x: x['modified'], reverse=True):
            table_rows.append(f"<tr><td>{log_file['name']}</td><td>{format_bytes(log_file['size'])}</td><td>{log_file['modified'][:19]}</td></tr>")
        log_table_html = f"""
        <table style="margin-top: 20px;">
            <thead>
                <tr>
                    <th>File Name</th>
                    <th>Size</th>
                    <th>Last Modified</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
        """
    else:
        log_table_html = '<p style="margin-top: 20px; color: var(--text-secondary);">No log files found</p>'

    content = f"""
    <style>
        .storage-section {{
            margin-bottom: 30px;
        }}
        .storage-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .info-card {{
            background: var(--bg-tertiary);
            padding: 15px;
            border-radius: 8px;
        }}
        .info-label {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 5px;
        }}
        .info-value {{
            font-size: 18px;
            font-weight: 600;
        }}
    </style>

    <div class="card storage-section">
        <h2 class="card-title">Database Storage</h2>
        <div class="storage-info">
            <div class="info-card">
                <div class="info-label">Database Path</div>
                <div class="info-value">{str(db_path)}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Database Size</div>
                <div class="info-value">{format_bytes(db_size)}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Status</div>
                <div class="info-value">{'✅ Exists' if _fs.exists(str(db_path)) else '❌ Not Found'}</div>
            </div>
        </div>
        <div style="margin-top: 20px;">
            <a href="/messages" class="btn btn-primary">View Messages</a>
            <a href="/deliveries" class="btn btn-primary">View Deliveries</a>
        </div>
    </div>

    <div class="card storage-section">
        <h2 class="card-title">Log Files Storage</h2>
        <div class="storage-info">
            <div class="info-card">
                <div class="info-label">Log Directory</div>
                <div class="info-value">{str(log_dir)}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Total Log Size</div>
                <div class="info-value">{format_bytes(total_log_size)}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Log Files</div>
                <div class="info-value">{len(log_files)} files</div>
            </div>
        </div>
        <div style="margin-top: 20px;">
            <a href="/logs" class="btn btn-primary">View Logs</a>
        </div>
        {log_table_html}
    </div>

    <div class="card storage-section">
        <h2 class="card-title">Message Storage</h2>
        <div class="storage-info">
            <div class="info-card">
                <div class="info-label">Total Messages</div>
                <div class="info-value">{total_messages:,}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Total Deliveries</div>
                <div class="info-value">{total_deliveries:,}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Estimated Message Storage</div>
                <div class="info-value">{format_bytes(estimated_message_storage)}</div>
            </div>
            <div class="info-card">
                <div class="info-label">Storage Location</div>
                <div class="info-value">Database</div>
            </div>
        </div>
        <div style="margin-top: 20px;">
            <a href="/messages" class="btn btn-primary">View Messages</a>
            <a href="/deliveries" class="btn btn-primary">View Deliveries</a>
        </div>
    </div>
"""
    html = get_base_layout("Storage Management", "storage", content, user)
    return HTMLResponse(content=html)


# API Documentation page - Fixed

async def api_docs(request: Request, user: str = Depends(get_current_user)):
    """API documentation page with embedded Swagger UI"""
    return _ui_index_response()
    content = f"""
    <style>
        .api-docs-container {{
            width: 100%;
            height: 80vh;
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        .api-docs-iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        .api-links {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}
    </style>

    <div class="api-links">
        <a href="{api_base_url}/docs" target="_blank" class="btn btn-primary">Open Swagger UI (New Tab)</a>
        <a href="{api_base_url}/redoc" target="_blank" class="btn btn-secondary">Open ReDoc (New Tab)</a>
        <a href="{api_base_url}/openapi.json" target="_blank" class="btn btn-secondary">OpenAPI JSON</a>
    </div>

    <div class="card">
        <h2 class="card-title">API Documentation</h2>
        <div class="api-docs-container">
            <iframe src="{api_base_url}/docs" class="api-docs-iframe" title="API Documentation"></iframe>
        </div>
    </div>
"""
    html = get_base_layout("API Documentation", "api-docs", content, user)
    return HTMLResponse(content=html)


# Platform health via create_health_router().
_web_health_paths = {"/health", "/ready", "/live", "/status"}
app.router.routes = [
    r for r in app.router.routes if getattr(r, "path", None) not in _web_health_paths
]
_web_env_file = ""
if config:
    _web_env_file = str(config.get("app.env_file") or "")
app.include_router(create_health_router(
    application_name="notification-agent-mcp-server",
    version="0.1.0",
    env_file=_web_env_file,
))


# Helper function to generate navigation menu

def get_nav_menu(current_page="dashboard"):
    """Generate navigation menu HTML"""
    nav_items = [
        ("/dashboard", "📊 Dashboard", "dashboard"),
        ("/db/users", "👥 Users", "users"),
        ("/db/groups", "👨‍👩‍👧‍👦 Groups", "groups"),
        ("/groups/add", "➕ Create Group", "groups-add"),
        ("/db/channels", "📡 Channels", "channels"),
        ("/db/messages", "💬 Messages", "messages"),
        ("/db/deliveries", "📦 Deliveries", "deliveries"),
        ("/services", "🔧 Services", "services"),
        ("/db/config", "⚙️ Configuration", "config"),
        ("/db/prompts", "📝 Prompts", "prompts"),
        ("/web-mcp-test", "🔧 MCP/A2A Testing", "mcp-test"),
        ("/logs", "📋 Logs", "logs"),
        ("/settings", "⚙️ Settings", "settings"),
        ("/web-api-docs", "📖 API Docs", "api-docs"),
    ]

    nav_html = '<div class="nav-menu">'
    for url, label, page_id in nav_items:
        active = 'active' if current_page == page_id else ''
        nav_html += f'<a href="{url}" class="nav-item {active}">{label}</a>'
    nav_html += '</div>'
    return nav_html


# Helper function to get user statistics

async def get_user_stats(user_id: int, username: str):
    """Get user statistics: message count, last message, groups"""
    try:
        config = get_config()
        db_uri = _require_config(config.get("db.uri"), "db.uri")
        db = get_db_manager(db_uri)
        db.connect()

        try:
            # Get message count (messages created by this user)
            msg_count_row = db.fetchone(
                "SELECT COUNT(*) as count FROM messages WHERE created_by = ?",
                (username,)
            )
            msg_count = msg_count_row.get("count", 0) if msg_count_row else 0

            # Get last message
            last_msg_row = db.fetchone(
                "SELECT id, created_at FROM messages WHERE created_by = ? ORDER BY created_at DESC LIMIT 1",
                (username,)
            )
            last_message_id = last_msg_row.get("id") if last_msg_row else None
            last_message_date = last_msg_row.get("created_at") if last_msg_row else None

            # Get groups
            from ...database.repositories import GroupMemberRepository
            member_repo = GroupMemberRepository(db)
            user_groups = member_repo.get_user_groups(user_id)
            group_names = [g.get("name", "") for g in user_groups]

            return {
                "message_count": msg_count,
                "last_message_id": last_message_id,
                "last_message_date": last_message_date,
                "groups": group_names
            }
        finally:
            # DatabaseManager manages its own connections - no need to close
            pass
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {"message_count": 0, "last_message_id": None, "last_message_date": None, "groups": []}


# Users page with left menu and all functionality

async def get_group_stats(group_id: int, group_name: str):
    """Get group statistics: member count, last message, message count"""
    try:
        config = get_config()
        db_uri = _require_config(config.get("db.uri"), "db.uri")
        db = get_db_manager(db_uri)
        db.connect()

        try:
            from ...database.repositories import GroupMemberRepository, MessageRepository

            # Get member count
            member_repo = GroupMemberRepository(db)
            members = member_repo.get_group_members(group_id)
            member_count = len(members)

            # Get messages sent to this group (messages with group:GroupName in destinations)
            # Note: This is approximate - we'd need to parse message destinations
            # For now, we'll count messages that mention the group name
            msg_repo = MessageRepository(db)
            all_messages = msg_repo.list_all(limit=10000)

            # Count messages that might be for this group (heuristic)
            group_msg_count = 0
            last_group_message = None
            for msg in all_messages:
                content_json = msg.get("content_json", "{}")
                if group_name.lower() in content_json.lower():
                    group_msg_count += 1
                    if not last_group_message or msg.get("created_at", "") > last_group_message.get("created_at", ""):
                        last_group_message = msg

            return {
                "member_count": member_count,
                "message_count": group_msg_count,
                "last_message_id": last_group_message.get("id") if last_group_message else None,
                "last_message_date": last_group_message.get("created_at") if last_group_message else None
            }
        finally:
            # DatabaseManager manages its own connections - no need to close
            pass
    except Exception as e:
        logger.error(f"Error getting group stats: {e}")
        return {"member_count": 0, "message_count": 0, "last_message_id": None, "last_message_date": None}


# Groups page with left menu and all functionality

async def view_message(request: Request, message_identifier: str, user: str = Depends(get_current_user),
                       format: Optional[str] = None):
    """View individual message - proxies to API server"""
    return _ui_index_response()
    try:
        # Proxy to API server with authentication
        params = {}
        if format:
            params["format"] = format

        # Get message from API server with longer timeout (may need to render HTML/format content)
        message_data = await api_request("GET", f"/messages/{message_identifier}", params=params, timeout=60.0)

        # If API returns HTML, display it in a card
        if isinstance(message_data, str) and "<html" in message_data.lower():
            content = f"""
    <div class="card">
        <div style="margin-bottom: 20px;">
            <a href="/messages" class="btn btn-secondary">← Back to Messages</a>
        </div>
        <div style="border: 1px solid var(--border); border-radius: 8px; padding: 20px;">
            {message_data}
        </div>
    </div>
"""
        else:
            # If JSON, format it nicely
            import json
            content = f"""
    <div class="card">
        <h2>Message: {message_identifier}</h2>
        <div style="margin-bottom: 20px;">
            <a href="/messages" class="btn btn-secondary">← Back to Messages</a>
            <a href="/messages/{message_identifier}?format=html" class="btn btn-primary">View as HTML</a>
            <a href="/messages/{message_identifier}?format=json" class="btn btn-secondary">View as JSON</a>
        </div>
        <pre style="background: var(--bg-tertiary); padding: 20px; border-radius: 8px; overflow-x: auto;">{json.dumps(message_data, indent=2)}</pre>
    </div>
"""
        html = get_base_layout(f"Message: {message_identifier}", "messages", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error viewing message: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


# Messages page with left menu, TTL fix, Create button, select/delete, sort/search, View

async def view_logs(request: Request, user: str = Depends(get_current_user),
                    log_type: str = "api_server", lines: int = 100):
    """View server logs with follow, wrap, refresh options"""
    return _ui_index_response()
    from pathlib import Path

    # Map log types to log file paths
    log_file_map = {
        "api_server": config.get("log.api_server_log", "./logs/api_server.log"),
        "web_server": config.get("log.web_server_log", "./logs/web_server.log"),
        "mcp_server": config.get("log.mcp_server_log", "./logs/mcp_server.log"),
        "a2a_server": config.get("log.a2a_server_log", "./logs/a2a_server.log"),
    }

    log_file_path_str = str(Path(log_file_map.get(log_type, log_file_map["api_server"])))

    # Read log content
    log_content = ""
    if _fs.exists(log_file_path_str):
        try:
            all_lines = _fs.read_bytes(log_file_path_str).decode("utf-8", errors="ignore").splitlines(True)
            log_content = ''.join(all_lines[-lines:]) if len(all_lines) > lines else ''.join(all_lines)
        except Exception as e:
            log_content = f"Error reading log file: {e}"
    else:
        log_content = f"Log file not found: {log_file_path_str}"

    content = f"""
    <style>
        .log-controls {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .log-content {{
            background: #1a1a2e;
            color: #e0e0e0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 70vh;
            overflow-y: auto;
            white-space: pre;
            word-wrap: break-word;
        }}
        .log-content.wrap {{
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        select, input[type="number"] {{
            padding: 6px 10px;
            border-radius: 4px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }}
        label {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 14px;
        }}
        .log-status {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-left: auto;
        }}
    </style>

    <div class="log-controls">
        <select id="log-type" onchange="refreshLogs()" style="padding: 8px;">
            <option value="api_server" {'selected' if log_type == 'api_server' else ''}>API Server Log</option>
            <option value="web_server" {'selected' if log_type == 'web_server' else ''}>Web Server Log</option>
            <option value="mcp_server" {'selected' if log_type == 'mcp_server' else ''}>MCP Server Log</option>
            <option value="a2a_server" {'selected' if log_type == 'a2a_server' else ''}>A2A Server Log</option>
        </select>
        <select id="log-lines" onchange="refreshLogs()" style="padding: 8px;">
            <option value="50" {'selected' if lines == 50 else ''}>50 lines</option>
            <option value="100" {'selected' if lines == 100 else ''}>100 lines</option>
            <option value="200" {'selected' if lines == 200 else ''}>200 lines</option>
            <option value="500" {'selected' if lines == 500 else ''}>500 lines</option>
            <option value="1000" {'selected' if lines == 1000 else ''}>1000 lines</option>
        </select>
        <select id="auto-refresh" onchange="setAutoRefresh()" style="padding: 8px;">
            <option value="0">Auto-refresh Off</option>
            <option value="5">Every 5s</option>
            <option value="10">Every 10s</option>
            <option value="30">Every 30s</option>
        </select>
        <label>
            <input type="checkbox" id="log-follow" onchange="setFollow()">
            Follow
        </label>
        <label>
            <input type="checkbox" id="log-wrap" onchange="toggleWrap()" checked>
            Wrap
        </label>
        <button onclick="refreshLogs()" class="btn btn-primary">Refresh</button>
        <button onclick="clearLogs()" class="btn btn-secondary">Clear</button>
        <span class="log-status" id="log-status">Last refresh: Never</span>
    </div>

    <div class="card">
        <div id="log-container" class="log-content wrap">{log_content}</div>
    </div>

    <script>
        let autoRefreshInterval = null;

        function refreshLogs() {{
            const logType = document.getElementById('log-type').value;
            const lines = document.getElementById('log-lines').value;
            const url = `/logs?log_type=${{logType}}&lines=${{lines}}`;
            window.location.href = url;
        }}

        function setAutoRefresh() {{
            const interval = parseInt(document.getElementById('auto-refresh').value);
            if (autoRefreshInterval) {{
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }}
            if (interval > 0) {{
                autoRefreshInterval = setInterval(refreshLogs, interval * 1000);
            }}
        }}

        function setFollow() {{
            if (document.getElementById('log-follow').checked) {{
                const container = document.getElementById('log-container');
                container.scrollTop = container.scrollHeight;
            }}
        }}

        function toggleWrap() {{
            const container = document.getElementById('log-container');
            if (document.getElementById('log-wrap').checked) {{
                container.classList.add('wrap');
            }} else {{
                container.classList.remove('wrap');
            }}
        }}

        function clearLogs() {{
            document.getElementById('log-container').textContent = '';
        }}

        // Auto-scroll to bottom on load if follow is enabled
        window.addEventListener('load', () => {{
            if (document.getElementById('log-follow').checked) {{
                const container = document.getElementById('log-container');
                container.scrollTop = container.scrollHeight;
            }}
            document.getElementById('log-status').textContent = `Last refresh: ${{new Date().toLocaleTimeString('en-UK')}}`;
        }});
    </script>
"""
    html = get_base_layout("Logs", "logs", content, user)
    return HTMLResponse(content=html)


# MCP Logs page (separate from main logs)

async def view_mcp_logs(request: Request, user: str = Depends(get_current_user), lines: int = 100):
    """View MCP server logs specifically"""
    return _ui_index_response()
    from pathlib import Path

    log_file_path_str = str(Path(config.get("log.mcp_server_log", "./logs/mcp_server.log")))

    log_content = ""
    if _fs.exists(log_file_path_str):
        try:
            all_lines = _fs.read_bytes(log_file_path_str).decode("utf-8", errors="ignore").splitlines(True)
            log_content = ''.join(all_lines[-lines:]) if len(all_lines) > lines else ''.join(all_lines)
        except Exception as e:
            log_content = f"Error reading log file: {e}"
    else:
        log_content = f"Log file not found: {log_file_path_str}"

    content = f"""
    <style>
        .log-controls {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .log-content {{
            background: #1a1a2e;
            color: #e0e0e0;
            padding: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 70vh;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>

    <div class="log-controls">
        <select id="log-lines" onchange="refreshLogs()" style="padding: 8px;">
            <option value="50" {'selected' if lines == 50 else ''}>50 lines</option>
            <option value="100" {'selected' if lines == 100 else ''}>100 lines</option>
            <option value="200" {'selected' if lines == 200 else ''}>200 lines</option>
            <option value="500" {'selected' if lines == 500 else ''}>500 lines</option>
        </select>
        <button onclick="refreshLogs()" class="btn btn-primary">Refresh</button>
    </div>

    <div class="card">
        <div id="log-container" class="log-content">{log_content}</div>
    </div>

    <script>
        function refreshLogs() {{
            const lines = document.getElementById('log-lines').value;
            window.location.href = `/mcp-logs?lines=${{lines}}`;
        }}
    </script>
"""
    html = get_base_layout("MCP Logs", "logs", content, user)
    return HTMLResponse(content=html)


# Settings page - Combined configuration view (OS env + env file + config.yaml + defaults.yaml)

async def view_settings(request: Request, user: str = Depends(get_current_user)):
    """View merged configuration and source layers."""
    return _ui_index_response()
    import yaml
    from pathlib import Path
    from cloud_dog_config.env_parser import parse_env_file

    def _parse_env_file_lenient(path: Path) -> dict:
        try:
            return parse_env_file(str(path))
        except Exception:
            parsed: dict[str, str] = {}
            raw_text = _fs.read_bytes(str(path)).decode("utf-8")
            for raw_line in raw_text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                parsed[key.strip()] = value.strip().strip('"').strip("'")
            return parsed

    try:
        defaults_yaml_path = str(Path("defaults.yaml"))
        config_yaml_path = str(Path("config.yaml"))

        default_config = {}
        config_yaml_data = {}
        env_file_data = {}
        env_build_data = {}

        if _fs.exists(defaults_yaml_path):
            default_config = yaml.safe_load(_fs.read_bytes(defaults_yaml_path).decode("utf-8")) or {}

        if _fs.exists(config_yaml_path):
            config_yaml_data = yaml.safe_load(_fs.read_bytes(config_yaml_path).decode("utf-8")) or {}

        for source_path_str, target in (("env", "env"), ("private/env-build", "env_build")):
            if not _fs.exists(source_path_str):
                continue
            parsed = _parse_env_file_lenient(Path(source_path_str))
            if target == "env":
                env_file_data = parsed
            else:
                env_build_data = parsed

        final_config = config.dump(mask_secrets=False)

        def flatten_dict(data, parent_key="", sep="."):
            items = []
            for key, value in data.items():
                new_key = f"{parent_key}{sep}{key}" if parent_key else key
                if isinstance(value, dict):
                    items.extend(flatten_dict(value, new_key, sep=sep).items())
                else:
                    items.append((new_key, value))
            return dict(items)

        default_flat = flatten_dict(default_config)
        config_yaml_flat = flatten_dict(config_yaml_data)
        env_build_flat = {k.replace("CLOUD_DOG__NOTIFY__", "").replace("__", ".").lower(): v for k, v in env_build_data.items()}
        env_file_flat = {k.replace("CLOUD_DOG__NOTIFY__", "").replace("__", ".").lower(): v for k, v in env_file_data.items()}
        final_flat = flatten_dict(final_config)
        runtime_sources = list(config.get_sources()) if hasattr(config, "get_sources") else []

        def mask_secret(key, value):
            secret_keys = ["password", "pwd", "token", "api_key", "secret", "key", "authorization"]
            if any(secret_key in key.lower() for secret_key in secret_keys):
                return "***MASKED***" if value else ""
            return str(value) if not isinstance(value, (dict, list)) else json.dumps(value)

        content = f"""
    <style>
        .config-section {{
            margin-bottom: 30px;
        }}
        .config-section h3 {{
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--primary);
            color: var(--primary);
        }}
        .config-table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-secondary);
            border-radius: 8px;
            overflow: hidden;
        }}
        .config-table th {{
            background: var(--bg-tertiary);
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            color: var(--text-secondary);
            width: 40%;
        }}
        .config-table td {{
            padding: 12px;
            border-top: 1px solid var(--border);
            font-family: 'Courier New', monospace;
            font-size: 12px;
            word-break: break-all;
        }}
        .config-table tr:hover {{
            background: var(--bg-tertiary);
        }}
        .config-value {{
            background: rgba(102, 126, 234, 0.1);
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .info-box {{
            background: var(--bg-tertiary);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid var(--info);
        }}
        .info-box p {{
            margin: 5px 0;
            font-size: 14px;
        }}
        .priority-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .priority-1 {{ background: #4CAF50; color: white; }}
        .priority-2 {{ background: #2196F3; color: white; }}
        .priority-3 {{ background: #ff9800; color: white; }}
        .priority-4 {{ background: #f44336; color: white; }}
    </style>

    <div class="info-box">
        <p><strong>Configuration Priority (Lowest to Highest):</strong></p>
        <p><span class="priority-badge priority-1">1. defaults.yaml</span> - Baseline defaults</p>
        <p><span class="priority-badge priority-2">2. config.yaml</span> - Custom overrides</p>
        <p><span class="priority-badge priority-3">3. env file(s)</span> - Environment specific values</p>
        <p><span class="priority-badge priority-4">4. OS Environment</span> - Highest priority (`CLOUD_DOG__*`)</p>
    </div>

    <div class="config-section">
        <h3>Runtime Sources ({len(runtime_sources)})</h3>
        <div class="card">
            <table class="config-table">
                <thead><tr><th>Source</th><th>Value</th></tr></thead>
                <tbody>
                    {''.join([f'<tr><td>source</td><td><span class="config-value">{mask_secret("source", s)}</span></td></tr>' for s in runtime_sources]) if runtime_sources else '<tr><td colspan="2">No runtime source metadata</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <div class="card">
        <h2 class="card-title">Final Merged Configuration ({len(final_flat)} settings)</h2>
        <table class="config-table">
            <thead>
                <tr>
                    <th>Key</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                {''.join([f'''
                <tr>
                    <td>{k}</td>
                    <td><span class="config-value">{mask_secret(k, v)}</span></td>
                </tr>
                ''' for k, v in sorted(final_flat.items())])}
            </tbody>
        </table>
    </div>

    <div class="config-section">
        <h3>Environment File: env ({len(env_file_flat)} settings)</h3>
        <div class="card">
            <table class="config-table">
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{k}</td>
                        <td><span class="config-value">{mask_secret(k, v)}</span></td>
                    </tr>
                    ''' for k, v in sorted(env_file_flat.items())]) if env_file_flat else '<tr><td colspan="2">No env file found or empty</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <div class="config-section">
        <h3>Environment File: private/env-build ({len(env_build_flat)} settings)</h3>
        <div class="card">
            <table class="config-table">
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{k}</td>
                        <td><span class="config-value">{mask_secret(k, v)}</span></td>
                    </tr>
                    ''' for k, v in sorted(env_build_flat.items())]) if env_build_flat else '<tr><td colspan="2">No private/env-build file found or empty</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <div class="config-section">
        <h3>config.yaml ({len(config_yaml_flat)} settings)</h3>
        <div class="card">
            <table class="config-table">
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{k}</td>
                        <td><span class="config-value">{mask_secret(k, v)}</span></td>
                    </tr>
                    ''' for k, v in sorted(config_yaml_flat.items())]) if config_yaml_flat else '<tr><td colspan="2">No config.yaml file found or empty</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>

    <div class="config-section">
        <h3>defaults.yaml ({len(default_flat)} settings)</h3>
        <div class="card">
            <table class="config-table">
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{k}</td>
                        <td><span class="config-value">{mask_secret(k, v)}</span></td>
                    </tr>
                    ''' for k, v in sorted(default_flat.items())]) if default_flat else '<tr><td colspan="2">No defaults.yaml file found or empty</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
"""
        html = get_base_layout("Configuration Settings", "settings", content, user)
        return HTMLResponse(content=html)
    except Exception as exc:
        logger.error(f"Error loading settings: {exc}")
        import traceback

        error_content = f"""
    <div class="card">
        <h2 class="card-title">Error Loading Configuration</h2>
        <p style="color: var(--danger);">{str(exc)}</p>
        <pre style="background: var(--bg-tertiary); padding: 15px; border-radius: 5px; overflow-x: auto;">{traceback.format_exc()}</pre>
    </div>
"""
        html = get_base_layout("Configuration Settings", "settings", error_content, user)
        return HTMLResponse(content=html)

async def view_user_page(request: Request, user_id: int, user: str = Depends(get_current_user)):
    """View user details page"""
    return _ui_index_response()
    try:
        user_data = await api_request("GET", _api_target_path(f"/users/{user_id}"))
        stats = await get_user_stats(user_id, user_data.get("username", ""))

        content = f"""
    <div class="card">
        <h2>User Details</h2>
        <table>
            <tr><th>ID</th><td>{user_data.get("id")}</td></tr>
            <tr><th>Username</th><td>{user_data.get("username")}</td></tr>
            <tr><th>Email</th><td>{user_data.get("email")}</td></tr>
            <tr><th>Display Name</th><td>{user_data.get("display_name", "")}</td></tr>
            <tr><th>Role</th><td>{user_data.get("role", "viewer")}</td></tr>
            <tr><th>Enabled</th><td>{'✅ Yes' if user_data.get("enabled", True) else '❌ No'}</td></tr>
            <tr><th>Language</th><td>{user_data.get("language", "en")}</td></tr>
            <tr><th>Preferred Channel</th><td>{user_data.get("preferred_channel", "")}</td></tr>
            <tr><th>Content Style</th><td>{user_data.get("content_style", "")}</td></tr>
            <tr><th>User Type</th><td>{user_data.get("user_type", "real")}</td></tr>
            <tr><th>Message Count</th><td>{stats.get("message_count", 0)}</td></tr>
            <tr><th>Last Message</th><td>{stats.get("last_message_date", "Never")}</td></tr>
            <tr><th>Groups</th><td>{', '.join(stats.get("groups", [])) or "None"}</td></tr>
        </table>
        <div style="margin-top: 20px;">
            <a href="/users/{user_id}/edit" class="btn btn-primary">Edit User</a>
            <a href="/users" class="btn btn-secondary">Back to Users</a>
        </div>
    </div>
"""
        html = get_base_layout(f"User: {user_data.get('username')}", "users", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error viewing user: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

@router.post("/messages/{message_id}/cancel")
async def cancel_message_web(request: Request, message_id: int, user: str = Depends(get_current_user)):
    """Cancel a message via Web UI"""
    try:
        await api_request("POST", f"/messages/{message_id}/cancel")
        return RedirectResponse(url=f"/messages/{message_id}", status_code=302)
    except Exception as e:
        logger.error(f"Error cancelling message: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


# ============================================================================
# SERVICE MANAGEMENT PAGES
# ============================================================================

# Services page - Fixed with left menu layout

async def view_services(request: Request, user: str = Depends(get_current_user)):
    """Service management and monitoring page"""
    return _ui_index_response()
    # Check permission
    user_data, checker = await get_user_with_permissions(request)
    if not checker.has_permission(ADMIN):
        raise HTTPException(status_code=403, detail="Permission denied: manage_services")
    # Get service statuses
    api_health = {"status": "unknown"}
    web_health = {"status": "unknown"}
    a2a_health = {"status": "unknown"}
    mcp_health = {"status": "unknown"}
    web_base_url = _require_config(config.get("web_server.base_url"), "web_server.base_url")
    a2a_base_url = _require_config(config.get("a2a_server.base_url"), "a2a_server.base_url")

    health_client = _get_internal_client()
    try:
        api_response = await health_client.get(f"{api_base_url}/health")
        api_health = api_response.json() if api_response.status_code == 200 else {"status": "unhealthy"}
    except Exception:
        api_health = {"status": "unavailable"}

    try:
        web_response = await health_client.get(f"{web_base_url}/health")
        web_health = web_response.json() if web_response.status_code == 200 else {"status": "unhealthy"}
    except Exception:
        web_health = {"status": "unavailable"}

    try:
        a2a_response = await health_client.get(f"{a2a_base_url}/health")
        a2a_health = a2a_response.json() if a2a_response.status_code == 200 else {"status": "unhealthy"}
    except Exception:
        a2a_health = {"status": "unavailable"}

    try:
        # MCP server doesn't have HTTP health endpoint, check if process exists
        mcp_health = {"status": "unknown", "note": "MCP server uses stdio, no HTTP endpoint"}
    except Exception:
        mcp_health = {"status": "unavailable"}

    def get_status_class(status):
        status_lower = status.lower()
        if status_lower == "healthy":
            return "status-sent"
        elif status_lower in ["unhealthy", "unavailable"]:
            return "status-failed"
        else:
            return "status-pending"

    content = f"""
    <style>
        .service-card {{
            margin-bottom: 20px;
        }}
        .service-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .service-name {{
            font-size: 18px;
            font-weight: 600;
        }}
        .service-actions {{
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }}
        .service-info {{
            margin-top: 10px;
            font-size: 14px;
            color: var(--text-secondary);
        }}
    </style>

    <div class="card service-card">
        <div class="service-header">
            <div>
                <div class="service-name">API Server (Port 8004)</div>
                <div class="service-info">REST API server for notification management</div>
            </div>
            <span class="status {get_status_class(api_health.get('status', 'unknown'))}">
                {api_health.get('status', 'unknown').upper()}
            </span>
        </div>
        <div class="service-actions">
            <button onclick="restartService('api')" class="btn btn-primary">Restart</button>
            <button onclick="refreshStatus()" class="btn btn-secondary">Refresh</button>
        </div>
    </div>

    <div class="card service-card">
        <div class="service-header">
            <div>
                <div class="service-name">Web UI Server (Port 8005)</div>
                <div class="service-info">Web interface for managing notifications</div>
            </div>
            <span class="status {get_status_class(web_health.get('status', 'unknown'))}">
                {web_health.get('status', 'unknown').upper()}
            </span>
        </div>
        <div class="service-actions">
            <button onclick="restartService('web')" class="btn btn-primary">Restart</button>
            <button onclick="refreshStatus()" class="btn btn-secondary">Refresh</button>
        </div>
    </div>

    <div class="card service-card">
        <div class="service-header">
            <div>
                <div class="service-name">A2A Server (Port {config.get('a2a_server.port', 8082)})</div>
                <div class="service-info">Agent-to-Agent WebSocket streaming server</div>
            </div>
            <span class="status {get_status_class(a2a_health.get('status', 'unknown'))}">
                {a2a_health.get('status', 'unknown').upper()}
            </span>
        </div>
        <div class="service-actions">
            <button onclick="restartService('a2a')" class="btn btn-primary">Restart</button>
            <button onclick="refreshStatus()" class="btn btn-secondary">Refresh</button>
        </div>
    </div>

    <div class="card service-card">
        <div class="service-header">
            <div>
                <div class="service-name">MCP Server (stdio)</div>
                <div class="service-info">Model Context Protocol server (stdio-based, no HTTP endpoint)</div>
            </div>
            <span class="status {get_status_class(mcp_health.get('status', 'unknown'))}">
                {mcp_health.get('status', 'unknown').upper()}
            </span>
        </div>
        <div class="service-actions">
            <button onclick="restartService('mcp')" class="btn btn-primary">Restart</button>
            <button onclick="refreshStatus()" class="btn btn-secondary">Refresh</button>
        </div>
    </div>

    <script>
        function restartService(service) {{
            if (!confirm(`Are you sure you want to restart the ${{service.toUpperCase()}} server?`)) {{
                return;
            }}
            alert('Service restart functionality requires system-level access. This is a placeholder.');
            // TODO: Implement actual service restart via systemd/docker/etc.
        }}

        function refreshStatus() {{
            location.reload();
        }}

        // Auto-refresh every 30 seconds
        setInterval(() => location.reload(), 30000);
    </script>
"""
    html = get_base_layout("Service Management", "services", content, user)
    return HTMLResponse(content=html)


# ============================================================================
# GROUP MANAGEMENT PAGES
# ============================================================================

def get_common_styles():
    """Get common CSS styles"""
    return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f5f7fa;
        }
        .nav {
            background: white;
            padding: 15px 40px;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 30px;
        }
        .nav a {
            margin-right: 20px;
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        .nav a:hover {
            text-decoration: underline;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 40px 40px;
        }
        h1 {
            color: #2d3748;
            margin-bottom: 20px;
        }
        .btn {
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            display: inline-block;
            margin-top: 10px;
        }
        .btn:hover {
            background: #5568d3;
        }
    """
