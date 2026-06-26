#!/usr/bin/env python3
"""
Start script for API Server
"""

import sys
import argparse
import uvicorn
import os
import faulthandler
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
    parser = argparse.ArgumentParser(description="Start Notification Agent API Server")
    parser.add_argument(
        "--env",
        type=str,
        help="Path to environment file (e.g., private/env-test-abc12345)"
    )
    args = parser.parse_args()
    
    if not args.env:
        print("❌ CRITICAL: --env flag is required (e.g., --env private/env-test)")
        sys.exit(1)
    
    env_file = args.env
    
    # Load configuration using the required env file
    config = get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        env_file=env_file,
        load_env_file=True,
        force_reload=True,
        unresolved_policy="empty",
    )

    # Export resolved runtime auth values before Uvicorn imports the app module.
    # The surrounding shell may source an env file directly, which can leave
    # placeholder values in ambient env vars; importing the app against those
    # placeholders causes the API auth middleware to seed the wrong bootstrap key.
    resolved_test_api_key = str(config.get("runtime.a2a_test_api_key") or "st-local-secret")
    resolved_api_key = str(config.get("api_server.api_key") or resolved_test_api_key)
    resolved_username = str(config.get("web_server.username") or "")
    resolved_password = str(config.get("web_server.password") or "").strip() or "st-local-secret"
    resolved_jwt_secret = str(config.get("auth.jwt_secret") or "").strip() or "st-web-session-secret"
    resolved_env = {
        "CLOUD_DOG__APP__ENV_FILE": env_file,
        "CLOUD_DOG__API_SERVER__API_KEY": resolved_api_key,
        "CLOUD_DOG__WEB_SERVER__USERNAME": resolved_username,
        "CLOUD_DOG__WEB_SERVER__PASSWORD": resolved_password,
        "CLOUD_DOG__AUTH__JWT_SECRET": resolved_jwt_secret,
        "CLOUD_DOG__RUNTIME__A2A_TEST_API_KEY": resolved_test_api_key,
        "CLOUD_DOG__NOTIFY__APP__ENV_FILE": env_file,
        "CLOUD_DOG__NOTIFY__API_SERVER__API_KEY": resolved_api_key,
        "CLOUD_DOG__NOTIFY__WEB_SERVER__USERNAME": resolved_username,
        "CLOUD_DOG__NOTIFY__WEB_SERVER__PASSWORD": resolved_password,
        "CLOUD_DOG__NOTIFY__AUTH__JWT_SECRET": resolved_jwt_secret,
        "CLOUD_DOG__NOTIFY__RUNTIME__A2A_TEST_API_KEY": resolved_test_api_key,
    }
    for key, value in resolved_env.items():
        if value:
            os.environ[key] = value

    env_path = str(config.get("app.env_file") or env_file).replace("\\", "/").lower()
    is_test_env = env_path.startswith("tests/") or "/tests/" in env_path
    if is_test_env:
        fault_log_path = Path(__file__).parent / "working" / "w28a-980-faulthandler.log"
        try:
            fault_log_path.parent.mkdir(parents=True, exist_ok=True)
            fault_log_handle = open(fault_log_path, "a", encoding="utf-8")
            fault_log_handle.write(
                f"\n=== start_api_server pid={os.getpid()} env={env_file} ===\n"
            )
            fault_log_handle.flush()
            faulthandler.enable(file=fault_log_handle, all_threads=True)
        except Exception:
            pass
    if not is_test_env:
        config.validate_startup_requirements()
    
    # Ensure LLM model is loaded if using Ollama
    llm_provider = config.get("llm.provider")
    if not llm_provider:
        raise RuntimeError("Missing required configuration: llm.provider")
    llm_provider = llm_provider.lower()
    if llm_provider == "ollama" and not is_test_env:
        from src.core.llm.ollama_model_manager import OllamaModelManager
        from src.utils.logger import get_logger
        
        logger = get_logger(__name__)
        base_url = config.get("llm.base_url")
        model_name = config.get("llm.model")
        auto_pull = config.get("llm.auto_pull")
        model_load_timeout = config.get("llm.model_load_timeout")
        if not base_url:
            raise RuntimeError("Missing required configuration: llm.base_url")
        if not model_name:
            raise RuntimeError("Missing required configuration: llm.model")
        if auto_pull is None or auto_pull == "":
            raise RuntimeError("Missing required configuration: llm.auto_pull")
        if model_load_timeout is None or model_load_timeout == "":
            raise RuntimeError("Missing required configuration: llm.model_load_timeout")
        
        print(f"⏳ Checking Ollama model availability...")
        print(f"   Base URL: {base_url}")
        print(f"   Model: {model_name}")
        
        ignore_tls = config.get("llm.ignore_tls")
        if ignore_tls is None or ignore_tls == "":
            raise RuntimeError("Missing required configuration: llm.ignore_tls")
        verify_ssl = not base_url.startswith('https://') or ignore_tls
        ollama_mgr = OllamaModelManager(
            base_url=base_url,
            logger=logger,
            auto_pull=auto_pull,
            verify_ssl=verify_ssl
        )
        
        if not ollama_mgr.ensure_model_loaded(model_name, auto_pull=auto_pull, max_wait=model_load_timeout):
            print(f"❌ Failed to ensure model '{model_name}' is loaded")
            print(f"   The API server will start, but LLM features will use fallback formatting")
        else:
            print(f"✅ Model '{model_name}' is ready")
    
    # Get server settings
    host = config.get("api_server.host")
    port = config.get("api_server.port")
    log_level = config.get("log.level")
    if not host:
        raise RuntimeError("Missing required configuration: api_server.host")
    if port is None or port == "":
        raise RuntimeError("Missing required configuration: api_server.port")
    if not log_level:
        raise RuntimeError("Missing required configuration: log.level")
    log_level = log_level.lower()
    
    print(f"Starting unified HTTP server on {host}:{port}")
    print(f"Swagger UI: http://{host}:{port}/docs")
    
    # Suppress uvicorn access logs (we use our own logging)
    from cloud_dog_logging import get_logger as platform_get_logger

    platform_get_logger("uvicorn.access").underlying_logger.setLevel(30)
    platform_get_logger("uvicorn").underlying_logger.setLevel(30)
    
    # Run server
    uvicorn.run(
        "src.servers.unified_app:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
        access_log=False,  # Disable access logs
    )


if __name__ == "__main__":
    main()
