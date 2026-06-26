#!/usr/bin/env python3
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

"""
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: Platform logging implementation used by src.utils.logger compatibility exports

Related Requirements: NF1.6
Related Tasks: T3
Related Architecture: CM1.1
Related Tests: UT1.1

Recent Changes (max 10):
- 2026-05-07: Moved implementation out of logger.py so the public logger shim remains <50 lines.

**************************************************
"""

import json
import os
from pathlib import Path
from types import MethodType
from typing import Any, Optional

# Access stdlib logging via __import__ for LogRecord factory injection
# (server_id enrichment). All public logger creation MUST go through
# cloud_dog_logging — _logging is used only for low-level record-factory
# manipulation and root-handler access that cloud_dog_logging does not expose.
_logging = __import__("logging")

from cloud_dog_logging import get_logger as platform_get_logger, setup_logging as platform_setup_logging
from cloud_dog_logging.correlation import set_environment, set_service_instance, set_service_name
from cloud_dog_logging.formatters import JSONFormatter, TextFormatter
from cloud_dog_logging.handlers import ConfigurableRotatingHandler, DualHandler

_SERVER_ID_FACTORY_INSTALLED = False
_SERVER_ID_CACHE: str | None = None
_APP_LOG_FILE_MODE = 0o644
_JSON_FORMATTER_PATCHED = False


def _resolve_server_id() -> str:
    """Resolve server_id from runtime config for all log records."""
    global _SERVER_ID_CACHE
    try:
        from src.config import get_config

        server_id = str(get_config().get("app.server_id") or "notification-agent").strip()
        _SERVER_ID_CACHE = server_id or "notification-agent"
    except Exception:
        _SERVER_ID_CACHE = _SERVER_ID_CACHE or "notification-agent"
    return _SERVER_ID_CACHE


def _resolve_service_instance() -> str:
    """Resolve stable service_instance metadata for all log records."""
    service_instance = _resolve_server_id()
    try:
        from src.config import get_config

        service_instance = str(
            get_config().get("service_instance") or get_config().get("app.server_id") or service_instance
        ).strip()
    except Exception:
        pass
    return service_instance or _resolve_server_id()


def _resolve_environment_name() -> str:
    """Resolve stable environment metadata for all log records.

    Per RULES.md §1.4 (zero bespoke env reads outside the config bootstrap
    carve-out), CLOUD_DOG_ENVIRONMENT MUST be read via cloud_dog_config rather
    than from the OS environment directly. The runtime config layer maps the
    environment-variable inputs into the merged config tree under the
    `environment` key (see config.runtime_config.RuntimeConfig).
    """
    environment = "dev"
    try:
        from src.config import get_config

        environment = str(get_config().get("environment") or environment).strip()
    except Exception:
        pass
    return environment or "dev"


def _ensure_server_id_record_factory() -> None:
    """Inject server_id into every LogRecord once, without touching call sites."""
    global _SERVER_ID_FACTORY_INSTALLED
    if _SERVER_ID_FACTORY_INSTALLED:
        return
    original_factory = _logging.getLogRecordFactory()

    def _factory(*args: Any, **kwargs: Any) -> _logging.LogRecord:
        record = original_factory(*args, **kwargs)
        if not hasattr(record, "server_id") or not getattr(record, "server_id"):
            record.server_id = _resolve_server_id()
        if not hasattr(record, "_platform_service_name") or not getattr(record, "_platform_service_name"):
            record._platform_service_name = _service_name_for(record.name)
        if not hasattr(record, "_platform_service_instance") or not getattr(record, "_platform_service_instance"):
            record._platform_service_instance = _resolve_service_instance()
        if not hasattr(record, "_platform_environment") or not getattr(record, "_platform_environment"):
            record._platform_environment = _resolve_environment_name()
        return record

    _logging.setLogRecordFactory(_factory)
    _SERVER_ID_FACTORY_INSTALLED = True


def _ensure_json_formatter_patch() -> None:
    """Normalize cloud_dog_logging JSON output before startup integrity records emit."""
    global _JSON_FORMATTER_PATCHED
    if _JSON_FORMATTER_PATCHED:
        return

    original_format = JSONFormatter.format

    def _patched_format(self: JSONFormatter, record: _logging.LogRecord) -> str:
        rendered = original_format(self, record)
        try:
            entry = json.loads(rendered)
        except Exception:
            return rendered

        entry["service"] = getattr(record, "_platform_service_name", None) or entry.get("service")
        entry["service_instance"] = getattr(record, "_platform_service_instance", None) or entry.get("service_instance")
        entry["environment"] = getattr(record, "_platform_environment", None) or entry.get("environment")
        entry["severity"] = entry.get("severity") or entry.get("level") or record.levelname
        entry["event_type"] = entry.get("event_type") or PlatformJSONFormatter._derive_event_type(record, entry)
        if isinstance(entry.get("extra"), dict):
            request_id = entry["extra"].get("request_id")
            if request_id and not entry.get("request_id"):
                entry["request_id"] = request_id
        return json.dumps(entry, default=str, ensure_ascii=False)

    JSONFormatter.format = _patched_format
    _JSON_FORMATTER_PATCHED = True


def _normalise_log_format(log_format: str) -> str:
    """Map legacy format names to cloud_dog_logging compat format names."""
    return "json" if (log_format or "").lower() == "json" else "text"


def _patch_file_handler_permissions(handler: Any, file_mode: int) -> None:
    """Override file handler permission enforcement for service-specific requirements."""
    file_handler = handler.file_handler if isinstance(handler, DualHandler) else handler
    if not hasattr(file_handler, "baseFilename"):
        return

    def _enforce_permissions(self: Any) -> None:
        try:
            os.chmod(Path(self.baseFilename).parent, 0o700)
        except OSError:
            pass
        if os.path.exists(self.baseFilename):
            try:
                os.chmod(self.baseFilename, file_mode)
            except OSError:
                pass

    file_handler._enforce_permissions = MethodType(_enforce_permissions, file_handler)
    file_handler._enforce_permissions()


def _patch_handler_formatter(handler: Any, formatter: _logging.Formatter) -> None:
    """Apply formatter to wrapped/inner handlers created by cloud_dog_logging."""
    handler.setFormatter(formatter)
    file_handler = getattr(handler, "file_handler", None)
    if file_handler is not None:
        file_handler.setFormatter(formatter)
    stream_handler = getattr(handler, "stream_handler", None)
    if stream_handler is not None:
        stream_handler.setFormatter(formatter)


def _formatter_for(log_format: str, service_name: str) -> _logging.Formatter:
    normalised = _normalise_log_format(log_format)
    if normalised == "json":
        return PlatformJSONFormatter(service_name=service_name)
    return TextFormatter(service_name=service_name)


def _service_name_for(name: str) -> str:
    service_name = "notification-agent-mcp-server"
    try:
        from src.config import get_config

        config = get_config()
        service_name = str(
            config.get("service_name")
            or config.get("app.server_name")
            or config.get("app.title")
            or service_name
        ).strip()
    except Exception:
        pass
    return service_name or name


def _apply_platform_context(name: str) -> None:
    """Populate cloud_dog_logging context so audit records carry service metadata.

    Environment metadata is sourced from cloud_dog_config (the `environment`
    key) rather than reading os.environ directly. See _resolve_environment_name
    for the rationale and RULES.md §1.4 for the binding rule.
    """
    service_name = _service_name_for(name)
    service_instance = _resolve_server_id()
    environment = "dev"
    try:
        from src.config import get_config

        config = get_config()
        service_instance = str(config.get("service_instance") or config.get("app.server_id") or service_instance).strip()
        environment = str(config.get("environment") or environment).strip()
    except Exception:
        pass
    set_service_name(service_name or name)
    set_service_instance(service_instance or _resolve_server_id())
    set_environment(environment or "dev")


def apply_platform_context(name: str) -> None:
    """Public wrapper for request-scoped middleware/hooks."""
    _apply_platform_context(name)


def _build_platform_config(
    *,
    name: str,
    log_file: str,
    log_level: str,
    log_format: str,
    console: bool,
) -> dict[str, Any]:
    """Build a full platform logging configuration for notification-agent.

    Environment metadata is sourced from cloud_dog_config (the `environment`
    key) rather than reading os.environ directly. See _resolve_environment_name
    for the rationale and RULES.md §1.4 for the binding rule.
    """
    service_name = _service_name_for(name)
    service_instance = _resolve_server_id()
    environment = "dev"
    try:
        from src.config import get_config

        config = get_config()
        service_instance = str(config.get("service_instance") or config.get("app.server_id") or service_instance).strip()
        environment = str(config.get("environment") or environment).strip()
    except Exception:
        pass
    return {
        "service_name": service_name or name,
        "service_instance": service_instance or _resolve_server_id(),
        "environment": environment or "dev",
        "log": {
            "level": str(log_level or "INFO").upper(),
            "format": _normalise_log_format(log_format),
            "console": bool(console),
            "app_log": log_file,
            "audit_log": "./logs/audit.log.jsonl",
        },
    }


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    log_level: str = "INFO",
    log_format: str = "standard",
    console: bool = True,
    max_bytes: int = 10485760,
    backup_count: int = 10,
) -> _logging.Logger:
    """Create a logger via cloud_dog_logging compatibility layer.

    `max_bytes` and `backup_count` remain for API compatibility with existing
    call sites; rotation is managed by cloud_dog_logging defaults in compat mode.
    """
    _ = max_bytes, backup_count
    _ensure_server_id_record_factory()
    _ensure_json_formatter_patch()
    _apply_platform_context(name)
    if not log_file:
        log_file = f"./logs/{name}.log"

    platform_setup_logging(
        _build_platform_config(
            name=name,
            log_file=log_file,
            log_level=log_level,
            log_format=log_format,
            console=console,
        )
    )
    formatter = _formatter_for(log_format, _service_name_for(name))
    for handler in _logging.root.handlers:
        _patch_handler_formatter(handler, formatter)
        _patch_file_handler_permissions(handler, _APP_LOG_FILE_MODE)
    return platform_get_logger(name).underlying_logger


def setup_sidecar_logger(
    name: str,
    log_file: str,
    log_level: str = "INFO",
    log_format: str = "json",
    max_bytes: int = 10485760,
    backup_count: int = 10,
) -> _logging.Logger:
    """Configure an additional cloud_dog_logging-formatted file logger."""
    _ensure_server_id_record_factory()
    _ensure_json_formatter_patch()
    _apply_platform_context(name)
    service_name = _service_name_for(name)
    logger = platform_get_logger(name).underlying_logger
    logger.setLevel(getattr(_logging, str(log_level or "INFO").upper(), _logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    handler = ConfigurableRotatingHandler(
        filename=log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
        rotation_mode="size",
        when="midnight",
        interval=1,
        compress=True,
        stream_name=name,
    )
    handler.setFormatter(_formatter_for(log_format, service_name))
    _patch_file_handler_permissions(handler, _APP_LOG_FILE_MODE)
    logger.addHandler(handler)
    return logger


def get_logger(name: str) -> _logging.Logger:
    """Get a logger by name without reconfiguring handlers."""
    _ensure_server_id_record_factory()
    return platform_get_logger(name).underlying_logger


class ContextLogger:
    """Logger wrapper that adds context to all log entries."""

    _RESERVED_LOG_KEYS = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def __init__(self, logger: _logging.Logger, **default_context: Any):
        self.logger = logger
        self.default_context = default_context

    def _add_context(self, **kwargs: Any) -> dict[str, Any]:
        # Avoid collisions with reserved LogRecord fields when using `extra=...`.
        filtered = {k: v for k, v in kwargs.items() if k not in self._RESERVED_LOG_KEYS}
        return {**self.default_context, **filtered}

    def debug(self, message: str, **context: Any) -> None:
        self.logger.debug(message, extra=self._add_context(**context))

    def info(self, message: str, **context: Any) -> None:
        self.logger.info(message, extra=self._add_context(**context))

    def warning(self, message: str, **context: Any) -> None:
        self.logger.warning(message, extra=self._add_context(**context))

    def error(self, message: str, **context: Any) -> None:
        self.logger.error(message, extra=self._add_context(**context))

    def exception(self, message: str, **context: Any) -> None:
        self.logger.exception(message, extra=self._add_context(**context))

    def critical(self, message: str, **context: Any) -> None:
        self.logger.critical(message, extra=self._add_context(**context))


def get_context_logger(name: str, **default_context: Any) -> ContextLogger:
    """Get a context logger with default context."""
    logger = get_logger(name)
    return ContextLogger(logger, **default_context)


class PlatformContextMiddleware:
    """Reapply stable service metadata for each request/task context."""

    def __init__(self, app: Any, logger_name: str) -> None:
        self.app = app
        self.logger_name = logger_name

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") in {"http", "websocket"}:
            _apply_platform_context(self.logger_name)
        await self.app(scope, receive, send)


class PlatformJSONFormatter(JSONFormatter):
    """Augment cloud_dog_logging JSON output with stable platform metadata."""

    @staticmethod
    def _derive_event_type(record: _logging.LogRecord, entry: dict[str, Any]) -> str:
        extra = entry.get("extra") if isinstance(entry.get("extra"), dict) else {}
        explicit = extra.get("event_type") if isinstance(extra, dict) else None
        if explicit:
            return str(explicit)

        message = str(entry.get("message") or "")
        logger_name = str(entry.get("logger") or record.name)

        if message == "Request started":
            return "http.request.started"
        if message == "Request completed":
            return "http.request.completed"
        if message == "a2a_request":
            return "a2a.request"
        if message == "audit_integrity_check" or logger_name == "cloud_dog_logging.integrity":
            return "audit.integrity"
        if logger_name.startswith("mcp."):
            if "CallToolRequest" in message:
                return "mcp.tool.call"
            if "ListToolsRequest" in message:
                return "mcp.tools.list"
            return "mcp.request"
        if logger_name == "web_access":
            return "web.access"
        if logger_name == "httpx":
            return "http.client"
        return "application.event"

    def format(self, record: _logging.LogRecord) -> str:
        entry = json.loads(super().format(record))
        entry["service"] = getattr(record, "_platform_service_name", None) or entry.get("service")
        entry["service_instance"] = getattr(record, "_platform_service_instance", None) or entry.get("service_instance")
        entry["environment"] = getattr(record, "_platform_environment", None) or entry.get("environment")
        entry["severity"] = entry.get("severity") or entry.get("level") or record.levelname
        entry["event_type"] = entry.get("event_type") or self._derive_event_type(record, entry)
        if isinstance(entry.get("extra"), dict):
            request_id = entry["extra"].get("request_id")
            if request_id and not entry.get("request_id"):
                entry["request_id"] = request_id
        return json.dumps(entry, default=str, ensure_ascii=False)
