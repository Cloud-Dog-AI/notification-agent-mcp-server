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


# Notification Agent MCP Server Control Script
# Reads configuration from env/defaults.yaml
# Based on the sql-agent-mcp-server server_control.sh

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PID_DIR=".pids"
mkdir -p "$PID_DIR" logs 2>/dev/null || true


# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Timing parameters - can be overridden via env
INITIAL_WAIT=${INITIAL_WAIT:-3}          # Wait after starting (seconds)
RETRY_INTERVAL=${RETRY_INTERVAL:-1}      # Time between checks (seconds)
MAX_WAIT=${MAX_WAIT:-15}                 # Max wait for start/stop (seconds)
SHUTDOWN_WAIT=${SHUTDOWN_WAIT:-10}       # Max wait for graceful shutdown (seconds)

# Server-specific timeouts (unified API needs more time for initialization)
# Allow env override because startup cost varies with real persisted test data.
API_MAX_WAIT=${API_MAX_WAIT:-120}
WORKER_MAX_WAIT=${WORKER_MAX_WAIT:-15}
WEB_MAX_WAIT=${WEB_MAX_WAIT:-60}
MCP_MAX_WAIT=${MCP_MAX_WAIT:-60}
A2A_MAX_WAIT=${A2A_MAX_WAIT:-60}

ALL_SERVERS=(api worker mcp web a2a)
STOP_SERVERS=(a2a web mcp worker api)

# Logging
log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }

ENV_FILE=""

if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
else
    PYTHON_BIN="python3"
fi

read_config() {
    local key=$1
    local default=$2
    local dotted_key
    dotted_key=$(printf '%s' "$key" | tr '[:upper:]' '[:lower:]' | sed 's/__/./g')
    "$PYTHON_BIN" - "$dotted_key" "$default" "$ENV_FILE" <<'PY'
import sys
sys.path.insert(0, ".")
from src.config import get_config

dotted_key = sys.argv[1]
default = sys.argv[2]
env_file = sys.argv[3]
cfg = get_config(
    defaults_yaml="defaults.yaml",
    config_yaml="config.yaml",
    env_file=env_file or "env",
    load_env_file=bool(env_file),
    force_reload=True,
    unresolved_policy="empty",
)
value = cfg.get(dotted_key)
if value is True:
    print("true")
elif value is False:
    print("false")
else:
    print(default if value is None or value == "" else value)
PY
}

# Get PID using port
get_port_pid() {
    local port=$1
    local pid=""

    if command -v lsof > /dev/null 2>&1; then
        pid=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1)
        [ -n "$pid" ] && { echo "$pid"; return 0; }
    fi

    if command -v ss > /dev/null 2>&1; then
        pid=$(ss -ltnp 2>/dev/null | grep ":$port " | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1)
        [ -n "$pid" ] && { echo "$pid"; return 0; }
    fi

    if command -v netstat > /dev/null 2>&1; then
        pid=$(netstat -tulpn 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 | grep -E '^[0-9]+$' | head -1)
        [ -n "$pid" ] && { echo "$pid"; return 0; }
    fi

    return 0
}

# Check if process is running
is_running() {
    local pid=$1
    [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1
}

# Check whether a PID belongs to the expected server script.
pid_matches_script() {
    local pid=$1
    local script_name=$2
    [ -n "$pid" ] || return 1
    [ -n "$script_name" ] || return 1
    is_running "$pid" || return 1

    local cmdline
    cmdline=$(ps -p "$pid" -o args= 2>/dev/null || true)
    printf '%s' "$cmdline" | grep -F -- "$script_name" > /dev/null 2>&1
}

# Initialize server configuration from config files
init_server_config() {
    # API Server
    API_PORT=$(read_config "API_SERVER__PORT" "8004")
    API_ENABLED=$(read_config "API_SERVER__ENABLED" "true")

    # Delivery Worker
    WORKER_PORT=$(read_config "DELIVERY_WORKER__PORT" "8024")
    WORKER_ENABLED=$(read_config "DELIVERY_WORKER__ENABLED" "true")

    # MCP Server
    MCP_PORT=$(read_config "MCP_SERVER__PORT" "8022")
    MCP_ENABLED=$(read_config "MCP_SERVER__ENABLED" "true")

    # Web UI Server
    WEB_PORT=$(read_config "WEB_SERVER__PORT" "8020")
    WEB_ENABLED=$(read_config "WEB_SERVER__ENABLED" "true")

    # A2A Server
    A2A_PORT=$(read_config "A2A_SERVER__PORT" "8023")
    A2A_ENABLED=$(read_config "A2A_SERVER__ENABLED" "true")

    # Server definitions: name:pid_file:port:script:log:enabled
    declare -g -A SERVERS
    SERVERS[api]="Unified HTTP Server:$PID_DIR/api_server.pid:$API_PORT:start_api_server.py:logs/api_server.log:$API_ENABLED"
    SERVERS[worker]="Delivery Worker:$PID_DIR/delivery_worker.pid:$WORKER_PORT:start_delivery_worker.py:logs/delivery_worker.log:$WORKER_ENABLED"
    SERVERS[mcp]="MCP Server:$PID_DIR/mcp_server.pid:$MCP_PORT:start_mcp_server.py:logs/mcp_server.log:$MCP_ENABLED"
    SERVERS[web]="Web UI Server:$PID_DIR/web_server.pid:$WEB_PORT:start_web_server.py:logs/web_server.log:$WEB_ENABLED"
    SERVERS[a2a]="A2A Server:$PID_DIR/a2a_server.pid:$A2A_PORT:start_a2a_server.py:logs/a2a_server.log:$A2A_ENABLED"
}

# Get server config
get_config() {
    local server=$1
    echo "${SERVERS[$server]}"
}

# Parse config
parse_config() {
    IFS=':' read -r name pid_file port script log enabled <<< "$1"
}

# Status check for single server
status_server() {
    local server=$1
    local config=$(get_config "$server")
    [ -z "$config" ] && { log_error "Unknown server: $server"; return 1; }
    
    parse_config "$config"
    
    # Check if server is enabled in config
    if [ "$enabled" != "true" ]; then
        echo -e "  ${YELLOW}○${NC} $name: ${YELLOW}Disabled in config${NC}"
        return 0
    fi
    
    local pid=""
    local pid_valid=false
    local port_pid=""
    local port_listening=false
    
    [ -f "$pid_file" ] && pid=$(cat "$pid_file")
    is_running "$pid" && pid_valid=true
    port_pid=$(get_port_pid "$port")
    [ -n "$port_pid" ] && port_listening=true
    
    # Network-based servers: check port binding
    if [ "$pid_valid" = true ] && [ "$port_listening" = true ] && [ "$port_pid" = "$pid" ]; then
        echo -e "  ${GREEN}✓${NC} $name: ${GREEN}Running${NC} (PID: $pid, Port: $port)"
        echo -e "    ${GREEN}✓${NC} Process running | ${GREEN}✓${NC} Port $port listening"
        return 0
    elif [ "$port_listening" = true ] && pid_matches_script "$port_pid" "$script"; then
        if [ "$pid" != "$port_pid" ]; then
            echo "$port_pid" > "$pid_file"
        fi
        echo -e "  ${GREEN}✓${NC} $name: ${GREEN}Running${NC} (PID: $port_pid, Port: $port) [recovered PID]"
        echo -e "    ${GREEN}✓${NC} Port $port listening | ${GREEN}✓${NC} Process matches $script"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name: ${RED}Not Running${NC}"
        
        if [ -n "$pid" ]; then
            [ "$pid_valid" = true ] && echo -e "    ${GREEN}✓${NC} Process PID:$pid running" || echo -e "    ${RED}✗${NC} Process PID:$pid DEAD"
        else
            echo -e "    ${RED}✗${NC} No PID file"
        fi
        
        if [ "$port_listening" = true ]; then
            if [ "$port_pid" = "$pid" ]; then
                echo -e "    ${GREEN}✓${NC} Port $port listening"
            else
                echo -e "    ${YELLOW}⚠${NC}  Port $port occupied by PID:$port_pid (WRONG PROCESS)"
            fi
        else
            echo -e "    ${RED}✗${NC} Port $port not listening"
        fi
        return 1
    fi
}

# Start single server
start_server() {
    local server=$1
    local config=$(get_config "$server")
    [ -z "$config" ] && { log_error "Unknown server: $server"; return 1; }
    
    parse_config "$config"
    
    # Check if server is enabled
    if [ "$enabled" != "true" ]; then
        log_warn "$name is disabled in configuration - skipping"
        return 0
    fi
    
    log_info "Starting $name (port: $port)..."
    
    # Check current status
    local pid=""
    local pid_valid=false
    [ -f "$pid_file" ] && pid=$(cat "$pid_file")
    is_running "$pid" && pid_valid=true
    
    local port_pid=$(get_port_pid "$port")
    
    # Handle states
    if [ "$pid_valid" = true ] && [ "$port_pid" = "$pid" ]; then
        log_warn "$name is already running (PID: $pid, Port: $port)"
        log_warn "Use 'stop $server' first, or 'restart $server'"
        return 1
    fi
    
    if [ "$pid_valid" = false ] && [ -f "$pid_file" ]; then
        log_warn "Found dead PID file (PID: $pid) - cleaning up"
        rm -f "$pid_file"
    fi
    
    if [ -n "$port_pid" ] && [ "$port_pid" != "$pid" ]; then
        log_error "Port $port is occupied by PID: $port_pid"
        log_error "Use 'force-stop $server' to kill it"
        return 1
    fi
    
    # Activate venv if it exists
    VENV_PYTHON="python3"
    if [ -d ".venv" ] && [ -f ".venv/bin/python3" ]; then
        VENV_PYTHON=".venv/bin/python3"
        log_info "Using virtual environment: .venv/"
    fi

    local runtime_log="${log%.log}.stdout.log"
    
    # Start detached in a new session so test harness subprocess exit does not reap the server.
    if command -v setsid > /dev/null 2>&1; then
        if [ -n "$ENV_FILE" ]; then
            setsid "$VENV_PYTHON" "$script" --env "$ENV_FILE" > "$runtime_log" 2>&1 < /dev/null &
        else
            setsid "$VENV_PYTHON" "$script" > "$runtime_log" 2>&1 < /dev/null &
        fi
    else
        if [ -n "$ENV_FILE" ]; then
            nohup "$VENV_PYTHON" "$script" --env "$ENV_FILE" > "$runtime_log" 2>&1 < /dev/null &
        else
            nohup "$VENV_PYTHON" "$script" > "$runtime_log" 2>&1 < /dev/null &
        fi
    fi
    local new_pid=$!
    echo "$new_pid" > "$pid_file"
    
    log_info "Waiting ${INITIAL_WAIT}s for startup..."
    sleep "$INITIAL_WAIT"
    
    # Use server-specific timeout or default
    local server_max_wait=$MAX_WAIT
    case "$server" in
        api) server_max_wait=$API_MAX_WAIT ;;
        worker) server_max_wait=$WORKER_MAX_WAIT ;;
        web) server_max_wait=$WEB_MAX_WAIT ;;
        mcp) server_max_wait=$MCP_MAX_WAIT ;;
        a2a) server_max_wait=$A2A_MAX_WAIT ;;
    esac
    
    # Validate network port binding.
    local elapsed=0
    
    # Network-based servers: validate port binding
    while [ $elapsed -lt $server_max_wait ]; do
        local actual_port_pid=$(get_port_pid "$port")
        if is_running "$new_pid"; then
            if [ "$actual_port_pid" = "$new_pid" ]; then
                log_success "$name started (PID: $new_pid, Port: $port)"
                return 0
            fi
        elif [ -n "$actual_port_pid" ] && pid_matches_script "$actual_port_pid" "$script"; then
            echo "$actual_port_pid" > "$pid_file"
            log_success "$name started (PID: $actual_port_pid, Port: $port) [recovered PID]"
            return 0
        else
            log_error "$name process died - check $log"
            rm -f "$pid_file"
            return 1
        fi
        
        sleep "$RETRY_INTERVAL"
        elapsed=$((elapsed + RETRY_INTERVAL))
    done
    
    log_error "$name failed to bind to port $port within ${server_max_wait}s"
    kill -9 "$new_pid" 2>/dev/null || true
    rm -f "$pid_file"
    return 1
}

# Stop single server
stop_server() {
    local server=$1
    local config=$(get_config "$server")
    [ -z "$config" ] && { log_error "Unknown server: $server"; return 1; }
    
    parse_config "$config"
    log_info "Stopping $name..."
    
    local pid=""
    local pid_valid=false
    [ -f "$pid_file" ] && pid=$(cat "$pid_file")
    is_running "$pid" && pid_valid=true
    
    local port_pid=$(get_port_pid "$port")
    
    # Handle states
    if [ "$pid_valid" = false ] && [ -z "$port_pid" ]; then
        if [ -f "$pid_file" ]; then
            log_warn "$name not running (dead PID: $pid) - cleaning up"
            rm -f "$pid_file"
        else
            log_warn "$name is not running"
        fi
        return 0
    fi
    
    if [ "$pid_valid" = false ] && [ -n "$port_pid" ]; then
        if pid_matches_script "$port_pid" "$script"; then
            pid="$port_pid"
            pid_valid=true
            echo "$pid" > "$pid_file"
            log_warn "Recovered $name PID from port $port (PID: $pid)"
        else
            log_error "PID invalid but port $port occupied by PID: $port_pid"
            log_error "Use 'force-stop $server'"
            return 1
        fi
    fi
    
    # Graceful stop
    log_info "Sending SIGTERM to $name (PID: $pid)..."
    kill -TERM "$pid" 2>/dev/null || true
    
    local elapsed=0
    while [ $elapsed -lt $SHUTDOWN_WAIT ]; do
        if ! is_running "$pid"; then
            log_success "$name stopped gracefully"
            rm -f "$pid_file"
            return 0
        fi
        sleep "$RETRY_INTERVAL"
        elapsed=$((elapsed + RETRY_INTERVAL))
    done
    
    # Force kill
    log_warn "$name did not stop gracefully, forcing..."
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
    rm -f "$pid_file"
    log_success "$name stopped (forced)"
    return 0
}

# Force stop single server
force_stop_server() {
    local server=$1
    local config=$(get_config "$server")
    [ -z "$config" ] && { log_error "Unknown server: $server"; return 1; }
    
    parse_config "$config"
    log_info "Force-stopping $name..."
    
    local pid=""
    [ -f "$pid_file" ] && pid=$(cat "$pid_file")
    local port_pid=$(get_port_pid "$port")
    
    # Kill PID file process
    if [ -n "$pid" ] && is_running "$pid"; then
        log_info "Killing PID: $pid..."
        kill -9 "$pid" 2>/dev/null || true
    fi
    
    # Kill port process
    if [ -n "$port_pid" ]; then
        log_info "Killing process on port $port (PID: $port_pid)..."
        kill -9 "$port_pid" 2>/dev/null || true
    fi
    
    rm -f "$pid_file"
    sleep "$RETRY_INTERVAL"
    
    if [ -z "$(get_port_pid "$port")" ]; then
        log_success "$name force-stopped"
        return 0
    else
        log_error "Port $port still occupied"
        return 1
    fi
}

# Parse command-line arguments for --env FIRST (before reading config)
ENV_FILE=""
ARGS=()
for arg in "$@"; do
    if [[ "$arg" == --env ]]; then
        ENV_FILE_NEXT=true
    elif [[ "$ENV_FILE_NEXT" == true ]]; then
        ENV_FILE="$arg"
        ENV_FILE_NEXT=false
    elif [[ "$arg" == --env=* ]]; then
        ENV_FILE="${arg#--env=}"
    else
        ARGS+=("$arg")
    fi
done

# CRITICAL: Validate ENV_FILE syntax if provided
# This prevents silent failures from malformed environment files
if [ -n "$ENV_FILE" ]; then
    if [ ! -f "$ENV_FILE" ]; then
        log_error "CRITICAL ERROR: Environment file does not exist: $ENV_FILE"
        log_error ""
        log_error "Please ensure the file exists and the path is correct."
        exit 1
    fi
    
    # Test bash syntax of env file
    if ! bash -n "$ENV_FILE" 2>/dev/null; then
        log_error "CRITICAL ERROR: Environment file has SYNTAX ERRORS: $ENV_FILE"
        log_error ""
        log_error "Bash syntax validation failed. Common issues:"
        log_error "  - Unmatched quotes (single or double)"
        log_error "  - Unescaped special characters in values"
        log_error "  - Missing closing brackets or braces"
        log_error ""
        log_error "Run this command to see detailed errors:"
        log_error "  bash -n $ENV_FILE"
        log_error ""
        log_error "This safety check prevents servers from starting with broken"
        log_error "configuration, which would cause silent failures and incorrect behavior."
        exit 1
    fi
fi

# CRITICAL: Enforce --env flag for ALL commands except help
# This prevents accidental use without proper environment configuration
case "${ARGS[0]:-}" in
    help|"")
        # Allow help and no-command status without --env
        ;;
    *)
        # All other commands REQUIRE --env flag
        if [ -z "$ENV_FILE" ]; then
            log_error "CRITICAL ERROR: --env flag is REQUIRED for all server operations"
            log_error ""
            log_error "This script MUST be run with: ./server_control.sh --env private/env-<name> <command>"
            log_error ""
            log_error "Examples:"
            log_error "  ./server_control.sh --env private/env-test-at16 status"
            log_error "  ./server_control.sh --env private/env-test-at16 start api"
            log_error "  ./server_control.sh --env private/env-test-at16 stop api"
            log_error ""
            log_error "This safety check prevents breaking production systems by ensuring"
            log_error "explicit environment configuration for ALL server operations."
            log_error ""
            log_error "Use './server_control.sh help' for more information"
            exit 1
        fi
        ;;
esac

# Initialize configuration (after ENV_FILE is set so read_config can use it)
if [ -n "$ENV_FILE" ]; then
    export CLOUD_DOG_ENV_FILES="$ENV_FILE"
fi
init_server_config

# Main commands
case "${ARGS[0]:-}" in
    start)
        servers=("${ARGS[@]:1}")
        if [ ${#servers[@]} -eq 0 ] || [[ " ${servers[*]} " == *" all "* ]]; then
            echo "Starting all enabled servers..."
            for s in "${ALL_SERVERS[@]}"; do start_server "$s" || true; done
        else
            for s in "${servers[@]}"; do start_server "$s" || true; done
        fi
        ;;
    stop)
        servers=("${ARGS[@]:1}")
        if [ ${#servers[@]} -eq 0 ] || [[ " ${servers[*]} " == *" all "* ]]; then
            echo "Stopping all servers..."
            for s in "${STOP_SERVERS[@]}"; do stop_server "$s" || true; done
        else
            for s in "${servers[@]}"; do stop_server "$s" || true; done
        fi
        ;;
    restart)
        servers=("${ARGS[@]:1}")
        restart_one() {
            local srv=$1
            if ! stop_server "$srv"; then
                log_warn "Graceful stop failed for $srv - attempting force-stop"
                force_stop_server "$srv" || return 1
            fi
            sleep 2
            if ! start_server "$srv"; then
                log_warn "Initial start failed for $srv - retrying once"
                force_stop_server "$srv" || true
                sleep 1
                start_server "$srv" || return 1
            fi
        }
        if [ ${#servers[@]} -eq 0 ] || [[ " ${servers[*]} " == *" all "* ]]; then
            if [ -n "$ENV_FILE" ]; then
                "$0" --env "$ENV_FILE" stop && sleep 2 && "$0" --env "$ENV_FILE" start
            else
                "$0" stop && sleep 2 && "$0" start
            fi
        else
            for s in "${servers[@]}"; do restart_one "$s" || exit 1; done
        fi
        ;;
    force-stop)
        servers=("${ARGS[@]:1}")
        if [ ${#servers[@]} -eq 0 ] || [[ " ${servers[*]} " == *" all "* ]]; then
            echo "Force-stopping all servers..."
            for s in "${STOP_SERVERS[@]}"; do force_stop_server "$s" || true; done
        else
            for s in "${servers[@]}"; do force_stop_server "$s" || true; done
        fi
        ;;
    status)
        echo "═══════════════════════════════════════════════════════════════════"
        echo "  Notification Agent MCP Server - Status"
        echo "  (Ports: HTTP=$API_PORT, Worker=$WORKER_PORT, MCP=$MCP_PORT, Web=$WEB_PORT, A2A=$A2A_PORT)"
        echo "═══════════════════════════════════════════════════════════════════"
        echo ""
        servers=("${ARGS[@]:1}")
        if [ ${#servers[@]} -eq 0 ] || [[ " ${servers[*]} " == *" all "* ]]; then
            for s in "${ALL_SERVERS[@]}"; do status_server "$s"; echo ""; done
        else
            for s in "${servers[@]}"; do status_server "$s"; echo ""; done
        fi
        echo "═══════════════════════════════════════════════════════════════════"
        ;;
    status-all)
        echo "═══════════════════════════════════════════════════════════════════"
        echo "  Notification Agent MCP Server - Status (All Servers)"
        echo "  (Ports: HTTP=$API_PORT, Worker=$WORKER_PORT, MCP=$MCP_PORT, Web=$WEB_PORT, A2A=$A2A_PORT)"
        echo "═══════════════════════════════════════════════════════════════════"
        echo ""
        for s in "${ALL_SERVERS[@]}"; do status_server "$s"; echo ""; done
        echo "═══════════════════════════════════════════════════════════════════"
        ;;
    start-all) [ -n "$ENV_FILE" ] && "$0" --env "$ENV_FILE" start || "$0" start ;;
    stop-all) [ -n "$ENV_FILE" ] && "$0" --env "$ENV_FILE" stop || "$0" stop ;;
    force-stop-all) [ -n "$ENV_FILE" ] && "$0" --env "$ENV_FILE" force-stop || "$0" force-stop ;;
    help)
        echo "═══════════════════════════════════════════════════════════════════"
        echo "  Notification Agent MCP Server - Help"
        echo "═══════════════════════════════════════════════════════════════════"
        echo ""
        echo "Usage: $0 [--env <file>] <command> [server]"
        echo ""
        echo "Options:"
        echo "  --env <file>        - Use custom environment file (e.g., private/env-test-idp)"
        echo ""
        echo "Commands:"
        echo "  start [server|all]      - Start server(s)"
        echo "  stop [server|all]       - Stop server(s) gracefully"
        echo "  restart [server|all]    - Restart server(s)"
        echo "  force-stop [server|all] - Force kill server(s)"
        echo "  status [server|all]     - Show status of one or all servers"
        echo "  status-all          - Show status of all servers"
        echo "  start-all           - Start all enabled servers"
        echo "  stop-all            - Stop all servers"
        echo "  force-stop-all      - Force stop all servers"
        echo "  help                - Show this help message"
        echo ""
        echo "Available Servers:"
        echo "  api    - Unified HTTP Server           (Port: $API_PORT)"
        echo "  worker - Delivery Worker               (Port: $WORKER_PORT)"
        echo "  mcp    - MCP Server                    (Port: $MCP_PORT)"
        echo "  web    - Web UI Server                 (Port: $WEB_PORT)"
        echo "  a2a    - A2A Server                    (Port: $A2A_PORT)"
        echo ""
        echo "Server Status:"
        for s in "${ALL_SERVERS[@]}"; do
            config=$(get_config "$s")
            parse_config "$config"
            if [ "$enabled" = "true" ]; then
                echo "  $s: Enabled in config"
            else
                echo "  $s: Disabled in config"
            fi
        done
        echo ""
        echo "Configuration is read from (in priority order):"
        if [ -n "$ENV_FILE" ]; then
            echo "  1. OS Environment variables (CLOUD_DOG__NOTIFY__<SERVER>__PORT)"
            echo "  2. Custom env file: $ENV_FILE (--env flag)"
            echo "  3. env file (CLOUD_DOG__NOTIFY__<SERVER>__PORT variables)"
            echo "  4. private/env-build file (BUILD PHASE - CLOUD_DOG__NOTIFY__<SERVER>__PORT)"
            echo "  5. defaults.yaml (fallback)"
        else
            echo "  1. OS Environment variables (CLOUD_DOG__NOTIFY__<SERVER>__PORT)"
            echo "  2. env file (CLOUD_DOG__NOTIFY__<SERVER>__PORT variables)"
            echo "  3. private/env-build file (BUILD PHASE - CLOUD_DOG__NOTIFY__<SERVER>__PORT)"
            echo "  4. defaults.yaml (fallback)"
        fi
        echo ""
        echo "Timing Parameters (can be set via environment):"
        echo "  INITIAL_WAIT=$INITIAL_WAIT        - Wait after starting (seconds)"
        echo "  RETRY_INTERVAL=$RETRY_INTERVAL      - Time between checks (seconds)"
        echo "  MAX_WAIT=$MAX_WAIT            - Default max wait for start/stop (seconds)"
        echo "  SHUTDOWN_WAIT=$SHUTDOWN_WAIT       - Max wait for graceful shutdown (seconds)"
        echo ""
        echo "Server-Specific Timeouts:"
        echo "  Unified HTTP Server: ${API_MAX_WAIT}s (needs time for DB + initialization)"
        echo "  Delivery Worker: ${WORKER_MAX_WAIT}s (needs DB + worker initialization)"
        echo "  Web UI Server: ${WEB_MAX_WAIT}s"
        echo "  MCP Server: ${MCP_MAX_WAIT}s"
        echo "  A2A Server: ${A2A_MAX_WAIT}s"
        echo ""
        echo "═══════════════════════════════════════════════════════════════════"
        ;;
    "")
        # No command - show status of all servers
        echo "═══════════════════════════════════════════════════════════════════"
        echo "  Notification Agent MCP Server - Status"
        echo "  (Ports: HTTP=$API_PORT, Worker=$WORKER_PORT, MCP=$MCP_PORT, Web=$WEB_PORT, A2A=$A2A_PORT)"
        echo "═══════════════════════════════════════════════════════════════════"
        echo ""
        for s in "${ALL_SERVERS[@]}"; do status_server "$s"; echo ""; done
        echo "═══════════════════════════════════════════════════════════════════"
        echo ""
        echo "Run './server_control.sh help' for available commands"
        ;;
    *)
        echo "Unknown command: $1"
        echo ""
        echo "Run './server_control.sh help' for available commands"
        exit 1
        ;;
esac
