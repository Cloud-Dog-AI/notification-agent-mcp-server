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
Description: LLM runtime client backed by cloud_dog_llm - provides
legacy-compatible connect/get_llm/invoke methods for notification codepaths.

Related Requirements: FR1.10, FR1.11
Related Tasks: T8
Related Architecture: CC3.1
Related Tests: UT1.6, IT1.15

**************************************************
"""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Thread as _Thread, Lock as _Lock, Event as _Event
import uuid
from typing import Any, Dict, Optional

from cloud_dog_llm import LLMRequest, Message, SessionContext, get_llm_client

from src.config import get_config
from src.core.reliability.circuit_breaker import CircuitBreaker
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMManager:
    """Compatibility wrapper that routes runtime calls through cloud_dog_llm."""

    SUPPORTED_PROVIDERS = [
        "ollama",
        "openai",
        "openrouter",
        "anthropic",
        "openai_compat",
        "vllm",
    ]

    def __init__(self, config=None):
        self.config = config or get_config()
        self.provider = str(self._require("provider")).lower()
        self.client = None
        self.llm = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[_Thread] = None
        self._loop_lock = _Lock()
        self._loop_ready = _Event()
        self._loop_init_timeout = float(self.config.get("llm.event_loop_init_timeout", 5) or 5)
        recovery_seconds = int(self.config.get("llm.circuit_breaker_recovery_seconds", 60) or 60)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=recovery_seconds,
            success_threshold=2,
            name="llm",
        )

    def _require(self, key: str) -> Any:
        value = self.config.get(f"llm.{key}")
        if value is None or value == "":
            raise RuntimeError(f"Missing required configuration: llm.{key}")
        return value

    def _get(self, key: str, default: Any = None) -> Any:
        return self.config.get(f"llm.{key}", default)

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Compatibility shim expected by formatter code paths."""
        return self._get(key, default)

    def _provider_id(self) -> str:
        provider = self.provider
        if provider == "azure":
            return "openai_compat"
        if provider in ("google", "bedrock"):
            return ""
        if provider == "openai":
            return "openai"
        return provider

    def _provider_api_key(self) -> str:
        provider = self.provider
        if provider == "openai":
            return str(self._get("openai_api_key", self._get("key", "")) or "")
        if provider == "anthropic":
            return str(self._get("anthropic_api_key", self._get("key", "")) or "")
        if provider == "azure":
            return str(self._get("azure_openai_api_key", self._get("key", "")) or "")
        if provider == "openrouter":
            return str(self._get("openrouter_api_key", self._get("key", "")) or "")
        return str(self._get("key", "")) or ""

    def _build_client_config(self) -> Dict[str, Any]:
        provider_id = self._provider_id()
        if not provider_id:
            raise RuntimeError(f"Unsupported provider for cloud_dog_llm: {self.provider}")

        base_url = str(self._require("base_url"))
        model = str(self._require("model"))
        query_timeout = float(self._get("query_timeout", self._get("timeout", 300)) or 300)
        translation_timeout = float(self._get("translation_timeout", query_timeout) or query_timeout)
        formatting_timeout = float(self._get("formatting_timeout", query_timeout) or query_timeout)
        summarization_timeout = float(self._get("summarization_timeout", query_timeout) or query_timeout)
        provider_timeout = max(
            query_timeout,
            translation_timeout,
            formatting_timeout,
            summarization_timeout,
        )

        provider_cfg: Dict[str, Any] = {
            "enabled": True,
            "base_url": base_url,
            "model": model,
            "api_key": self._provider_api_key(),
            "timeout_seconds": provider_timeout,
        }

        return {
            "llm": {"default_provider": provider_id},
            "providers": {provider_id: provider_cfg},
        }

    def _ensure_background_loop(self) -> asyncio.AbstractEventLoop:
        """Create a dedicated loop thread so async HTTP clients stay loop-consistent."""
        with self._loop_lock:
            if self._loop is not None and not self._loop.is_closed():
                # Verify the thread is still alive and the loop is running (W28A-984a Fix 5)
                if (
                    self._loop_thread is not None
                    and self._loop_thread.is_alive()
                    and self._loop.is_running()
                ):
                    return self._loop
                # Loop exists but thread is dead or loop stopped — recreate
                logger.warning("LLM background loop thread is dead, recreating")
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except Exception:
                    pass
                self._loop = None
                self._loop_thread = None

            self._loop_ready.clear()
            loop = asyncio.new_event_loop()

            def _runner():
                asyncio.set_event_loop(loop)
                self._loop_ready.set()
                loop.run_forever()

            thread = _Thread(target=_runner, daemon=True)
            thread.start()

            if not self._loop_ready.wait(timeout=self._loop_init_timeout):
                raise RuntimeError("Failed to initialise LLM background event loop")

            self._loop = loop
            self._loop_thread = thread
            return loop

    def _run_async(self, coro, timeout_seconds: float):
        """Run async work in a dedicated loop thread with a hard timeout."""
        loop = self._ensure_background_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=float(timeout_seconds))
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"LLM operation timed out after {timeout_seconds} seconds") from exc

    def connect(self) -> bool:
        """Initialise the cloud_dog_llm client."""
        provider_id = self._provider_id()
        if provider_id not in self.SUPPORTED_PROVIDERS:
            logger.error("Unsupported LLM provider: %s", self.provider)
            return False
        try:
            self.client = get_llm_client(self._build_client_config())
            health_timeout = float(self._get("health_timeout", 10) or 10)
            healthy = bool(self._run_async(self.client.health(), timeout_seconds=health_timeout))
            if not healthy:
                logger.error("LLM provider health check failed for provider=%s", provider_id)
                self.client = None
                self.llm = None
                return False
            self.llm = self
            return True
        except Exception as exc:
            logger.info("LLM client deferred (missing config): %s", exc)
            self.client = None
            self.llm = None
            return False

    def get_llm(self):
        if self.llm is None and not self.connect():
            return None
        return self.llm

    def get_circuit_state(self) -> str:
        """Expose the current circuit-breaker state to caller-side policy code."""
        try:
            state = self._circuit_breaker.get_state().get("state") or "closed"
        except Exception:
            state = "closed"
        return str(state).strip().lower() or "closed"

    def get_connection_status(self) -> str:
        """Return a stable monitoring label for the LLM connection path."""
        circuit_state = self.get_circuit_state()
        if circuit_state == "open":
            return "breaker_open"
        if circuit_state == "half_open":
            return "probing"
        return "connected" if self.is_healthy() else "disconnected"

    def is_healthy(self) -> bool:
        """Check if LLM is available (circuit not open).
        Returns True when client is not yet initialized (lazy connect)
        so the delivery worker attempts the first invoke, which triggers connect().
        """
        if self.get_circuit_state() == "open":
            return False
        # If client is None, it hasn't been lazily initialized yet — allow
        # the first invoke to trigger connect(). Only return False when the
        # circuit breaker has tripped (i.e., repeated actual failures).
        return True

    def invoke(self, prompt: str, timeout: int = 300, **kwargs) -> str:
        return self._circuit_breaker.call(self._invoke_impl, prompt, timeout=timeout, **kwargs)

    def _invoke_impl(self, prompt: str, timeout: int = 300, **kwargs) -> str:
        if not getattr(self, "client", None) and not self.connect():
            raise RuntimeError("LLM client is not connected")

        max_tokens = self._get("max_tokens", self._get("num_predict"))
        if max_tokens is not None and max_tokens != "":
            try:
                max_tokens = int(max_tokens)
            except (TypeError, ValueError):
                max_tokens = None
        else:
            max_tokens = None

        temperature = self._get("temperature")
        if temperature is not None and temperature != "":
            try:
                temperature = float(temperature)
            except (TypeError, ValueError):
                temperature = None
        else:
            temperature = None

        params: Dict[str, Any] = {}
        for key in (
            "top_p",
            "top_k",
            "repeat_penalty",
            "seed",
            "num_ctx",
            "num_predict",
            "mirostat",
            "mirostat_tau",
            "mirostat_eta",
            "stop",
        ):
            value = self._get(key)
            if value is not None and value != "":
                params[key] = value
        params.update(kwargs.get("params", {}))

        # Honour explicit per-request output budgets. Translation/formatting paths
        # pass a smaller num_predict, but the old behaviour still sent the global
        # max_tokens=32768 alongside it, which caused the backend to clamp and stall.
        effective_num_predict = params.get("num_predict")
        if effective_num_predict is not None and effective_num_predict != "":
            try:
                effective_num_predict = int(effective_num_predict)
            except (TypeError, ValueError):
                effective_num_predict = None
        if effective_num_predict is not None:
            if max_tokens is None:
                max_tokens = effective_num_predict
            else:
                max_tokens = min(max_tokens, effective_num_predict)

        # Never send an output budget that consumes the full context window.
        # A large number of legacy formatter paths do not pass params.num_predict,
        # so rely on the runtime client to enforce a sane ceiling.
        effective_num_ctx = params.get("num_ctx", self._get("num_ctx"))
        if effective_num_ctx is not None and effective_num_ctx != "":
            try:
                effective_num_ctx = int(effective_num_ctx)
            except (TypeError, ValueError):
                effective_num_ctx = None
        if max_tokens is not None and effective_num_ctx and max_tokens >= effective_num_ctx:
            # Legacy callers often inherit num_ctx=max_tokens=32768, which is
            # pathological for translation/summarisation requests. Use a sane
            # fallback ceiling rather than half the context window.
            max_tokens = max(512, min(2048, effective_num_ctx // 8))

        request = LLMRequest(
            provider_id=self._provider_id(),
            model=str(self._require("model")),
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[Message(role="user", content=str(prompt))],
            params=params,
        )
        session = SessionContext(
            session_id=f"notify-{uuid.uuid4().hex}",
            correlation_id=f"notify-{uuid.uuid4().hex}",
        )

        try:
            response = self._run_async(
                self.client.chat(request, session),
                timeout_seconds=float(timeout),
            )
        except KeyboardInterrupt:
            raise
        except BaseException as exc:  # noqa: BLE001
            # A provider/runtime failure must degrade a single delivery, not tear down
            # the whole notification API worker process.
            raise RuntimeError(
                f"LLM invocation failed with fatal exception: {type(exc).__name__}: {exc}"
            ) from exc
        if response is None or not str(response.content).strip():
            raise RuntimeError("LLM returned empty response")
        return str(response.content)

    def get_provider(self) -> str:
        return self.provider
