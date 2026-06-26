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

import asyncio
import inspect
from datetime import datetime
from typing import Any, Dict

from fastapi import Request

from ...config import get_config
from ...core import JobManager
from ...core.delivery_worker import DeliveryWorker
from ...database import get_db_manager
from ...database.repositories import DeliveryRepository
from ...utils.logger import PlatformContextMiddleware, setup_logger, get_logger
from cloud_dog_api_kit import create_app as platform_create_app, create_health_router
from cloud_dog_api_kit.lifecycle.hooks import LifecycleHooks


def _config_truthy(value: Any, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _require_config(value: Any, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


_temp_cfg = get_config(unresolved_policy="empty")
config = _temp_cfg
db = None
job_manager = None
delivery_worker = None
worker_task: asyncio.Task | None = None
logger = get_logger("delivery_worker_server")


def _runtime_config(*, force_reload: bool = False):
    global config
    if config is not None and not force_reload:
        return config
    config = get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        force_reload=force_reload,
        unresolved_policy="empty",
    )
    return config


def _queued_backlog() -> int:
    if db is None:
        return 0
    try:
        return DeliveryRepository(db).count_pending_backlog()
    except Exception:
        return 0


def _estimate_wait_seconds(queue_length: int) -> int:
    current_cfg = config or _temp_cfg
    max_concurrent = max(1, int(current_cfg.get("llm.max_concurrent", 3) or 3))
    avg_request_duration = float(current_cfg.get("llm.avg_request_duration", 60.0) or 60.0)
    if queue_length <= 0:
        return 0
    return max(1, int((queue_length * avg_request_duration) / max_concurrent))


async def _fallback_llm_status(connection_status: str = "worker_unavailable") -> Dict[str, Any]:
    current_cfg = config or _temp_cfg
    queue_length = _queued_backlog()
    max_concurrent = max(1, int(current_cfg.get("llm.max_concurrent", 3) or 3))
    avg_request_duration = float(current_cfg.get("llm.avg_request_duration", 60.0) or 60.0)
    estimated_wait_seconds = _estimate_wait_seconds(queue_length)
    return {
        "available": queue_length == 0,
        "active_requests": 0,
        "max_concurrent": max_concurrent,
        "queue_length": queue_length,
        "estimated_wait_seconds": estimated_wait_seconds if queue_length > 0 else 0,
        "connection_status": connection_status,
        "avg_request_duration": avg_request_duration,
    }


async def _llm_status_payload() -> Dict[str, Any]:
    if delivery_worker is not None and hasattr(delivery_worker, "llm_availability"):
        try:
            return await delivery_worker.llm_availability.get_queue_status()
        except Exception as exc:
            logger.warning(f"Delivery worker LLM status fallback engaged: {exc}")
    return await _fallback_llm_status()


def _worker_running() -> bool:
    return bool(
        delivery_worker is not None
        and getattr(delivery_worker, "running", False)
        and worker_task is not None
        and not worker_task.done()
    )


async def _db_health_check() -> dict:
    db_healthy = db.health_check() if db else False
    result: dict = {"status": "ok" if db_healthy else "error"}
    if db_healthy and db:
        try:
            result["dialect"] = db.get_dialect() or ""
        except Exception:
            pass
    return result


async def _worker_health_check() -> dict:
    return {
        "status": "ok" if _worker_running() else "error",
        "running": _worker_running(),
        "queue_backlog": _queued_backlog(),
    }


async def _startup(_: Any) -> None:
    global config, db, job_manager, delivery_worker, worker_task, logger

    config = _runtime_config(force_reload=True)
    logger = setup_logger(
        name="delivery_worker_server",
        log_file=_require_config(config.get("log.delivery_worker_log"), "log.delivery_worker_log"),
        log_level=_require_config(config.get("log.level"), "log.level"),
        log_format=_require_config(config.get("log.format"), "log.format"),
        console=_require_config(config.get("log.console"), "log.console"),
    )
    logger.info("Starting delivery worker server...")

    if not _config_truthy(config.get("delivery_worker.enabled", True), True):
        raise RuntimeError("Delivery worker server is disabled by configuration")

    db_uri = _require_config(config.get("db.uri"), "db.uri")
    db = get_db_manager(db_uri)

    try:
        db.initialize_schema()
        logger.info("Database schema initialized")
    except Exception as exc:
        error_message = str(exc).lower()
        if "duplicate column name" in error_message or "already exists" in error_message:
            logger.info(f"Schema initialization skipped: {exc}")
        else:
            raise

    job_manager = JobManager(
        db=db,
        default_ttl_hours=_require_config(config.get("queue.default_ttl_hours"), "queue.default_ttl_hours"),
        max_retries=_require_config(config.get("queue.max_retries"), "queue.max_retries"),
        backoff_base_seconds=_require_config(config.get("queue.backoff_base_seconds"), "queue.backoff_base_seconds"),
        backoff_max_seconds=_require_config(config.get("queue.backoff_max_seconds"), "queue.backoff_max_seconds"),
    )

    delivery_worker = DeliveryWorker(
        db=db,
        job_manager=job_manager,
        config=config,
        poll_interval=config.get("delivery_worker.poll_interval", 1.0),
        batch_size=config.get("delivery_worker.batch_size", 10),
    )
    worker_task = asyncio.create_task(delivery_worker.start())

    def _done_callback(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
        except asyncio.CancelledError:
            pass
        except BaseException:
            logger.exception("Delivery worker task terminated unexpectedly", exc_info=True)

    worker_task.add_done_callback(_done_callback)
    logger.info("Delivery worker server started successfully")


async def _shutdown(_: Any) -> None:
    global delivery_worker, worker_task

    if logger:
        logger.info("Stopping delivery worker server...")
    if delivery_worker is not None:
        delivery_worker.stop()
    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Delivery worker shutdown encountered an error", exc_info=True)
        worker_task = None
    delivery_worker = None


_lifecycle_hooks = LifecycleHooks(on_post_router=_startup, on_shutdown=_shutdown)
_app_kwargs = {
    "title": "Notification Agent Delivery Worker",
    "version": "0.1.0",
    "description": "Separate-process delivery worker for queued notification deliveries",
    "base_path": "",
    "enable_cors": False,
    "enable_docs": False,
    "enable_health": False,
    "register_signal_handlers_on_startup": False,
    "lifecycle_hooks": _lifecycle_hooks,
}
try:
    _create_app_sig = inspect.signature(platform_create_app)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in _create_app_sig.parameters.values()):
        app = platform_create_app(**_app_kwargs)
    else:
        app = platform_create_app(**{k: v for k, v in _app_kwargs.items() if k in _create_app_sig.parameters})
except (TypeError, ValueError):
    app = platform_create_app(**_app_kwargs)

app.add_middleware(PlatformContextMiddleware, logger_name="delivery_worker_server")

_health_env_file = str(_temp_cfg.get("app.env_file") or "")
_health_router = create_health_router(
    application_name="notification-agent-delivery-worker",
    version="0.1.0",
    env_file=_health_env_file,
    checks={"database": _db_health_check, "worker": _worker_health_check},
)
app.include_router(_health_router)
app.include_router(_health_router, prefix="/worker")


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "name": "Notification Agent Delivery Worker",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/worker/llm/status")
async def worker_llm_status(request: Request) -> Dict[str, Any]:
    del request
    return await _llm_status_payload()


@app.get("/worker/runtime")
async def worker_runtime_status() -> Dict[str, Any]:
    return {
        "running": _worker_running(),
        "queue_backlog": _queued_backlog(),
        "llm": await _llm_status_payload(),
        "timestamp": datetime.now().isoformat(),
    }
