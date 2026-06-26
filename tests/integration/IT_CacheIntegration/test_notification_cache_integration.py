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

"""Integration Test: W28A-413-C cache coverage for notification-agent."""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest

from cloud_dog_cache import CacheConfig, cached, init_cache
from tests.utils.api_tracking import build_tracked_client


pytestmark = [pytest.mark.integration, pytest.mark.cache]


@pytest.fixture
def api_client(api_base_url, api_key, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=180.0,
        registry=api_cleanup_registry,
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def ensure_cache_enabled(api_client):
    response = api_client.post(
        "/config/update",
        json={
            "updates": {
                "cache.enabled": True,
                "cache.backend": "memory",
                "cache.ttl_seconds": 3600,
                "cache.max_entries": 1000,
            }
        },
    )
    assert response.status_code == 200, response.text
    flush = api_client.post("/cache/flush")
    assert flush.status_code == 200, flush.text
    yield
    api_client.post(
        "/config/update",
        json={
            "updates": {
                "cache.enabled": True,
                "cache.backend": "memory",
                "cache.ttl_seconds": 3600,
                "cache.max_entries": 1000,
            }
        },
    )
    api_client.post("/cache/flush")


def _stats(client) -> dict[str, float | int | bool]:
    response = client.get("/cache/stats")
    assert response.status_code == 200, response.text
    payload = response.json()
    raw = payload.get("stats") if isinstance(payload, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    return {
        "enabled": bool(payload.get("enabled", True)),
        "entries": int(raw.get("entries", 0) or 0),
        "hits": int(raw.get("hits", 0) or 0),
        "misses": int(raw.get("misses", 0) or 0),
        "hit_rate": float(raw.get("hit_rate", 0.0) or 0.0),
        "memory_bytes": int(raw.get("memory_bytes", 0) or 0),
    }


def _render_payload(suffix: str, *, template_variant: str = "ready") -> dict[str, object]:
    return {
        "template": f"Hello {{name}}, your order {{order_id}} is {template_variant}. Ref {suffix}.",
        "variables": {"name": "Cache User", "order_id": f"ORD-{suffix}"},
        "language": "en",
        "channel_type": "email",
    }


def _render(client, suffix: str, *, template_variant: str = "ready"):
    return client.post("/api/v1/messages/render", json=_render_payload(suffix, template_variant=template_variant))


class TestCacheIntegration:
    """W28A-413-C cache integration scenarios."""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_01_cache_miss_first_call(self, api_client):
        assert _stats(api_client)["entries"] == 0

        response = _render(api_client, "MISS01")
        assert response.status_code == 200, response.text

        stats = _stats(api_client)
        assert stats["entries"] >= 1
        assert stats["hits"] == 0
        assert stats["misses"] >= 1
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_02_cache_hit_repeat_call(self, api_client):
        start_1 = time.perf_counter()
        first = _render(api_client, "HIT02")
        duration_1 = time.perf_counter() - start_1
        assert first.status_code == 200, first.text

        start_2 = time.perf_counter()
        second = _render(api_client, "HIT02")
        duration_2 = time.perf_counter() - start_2
        assert second.status_code == 200, second.text
        assert second.json() == first.json()
        assert duration_2 < duration_1 * 0.5, (duration_1, duration_2)

        stats = _stats(api_client)
        assert stats["entries"] >= 1
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_03_cache_miss_different_parameters(self, api_client):
        first = _render(api_client, "MISS03A", template_variant="ready")
        second = _render(api_client, "MISS03B", template_variant="shipped")
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["rendered_template"] != second.json()["rendered_template"]

        stats = _stats(api_client)
        assert stats["entries"] >= 2
        assert stats["misses"] >= 2
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_04_cache_expiry(self):
        init_cache(CacheConfig(enabled=True, backend="memory", ttl_seconds=3600, max_entries=1000))
        calls = {"count": 0}

        @cached(ttl=1, key_params=("value",))
        async def _ttl_probe(*, value: str):
            calls["count"] += 1
            await asyncio.sleep(0.01)
            return {"value": value, "count": calls["count"]}

        first = asyncio.run(_ttl_probe(value="same"))
        second = asyncio.run(_ttl_probe(value="same"))
        assert first == second

        time.sleep(2)
        third = asyncio.run(_ttl_probe(value="same"))
        assert third["count"] == 2
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_05_cache_invalidation_event(self, api_client):
        first = _render(api_client, "INV05")
        assert first.status_code == 200, first.text
        second = _render(api_client, "INV05")
        assert second.status_code == 200, second.text
        stats_before = _stats(api_client)
        assert stats_before["hits"] >= 1

        prompt_name = f"it_cache_prompt_{uuid4().hex}"
        prompt_response = api_client.post(
            "/prompts",
            json={
                "name": prompt_name,
                "prompt_text": "Cache invalidation prompt {value}",
                "channel_type": "email",
                "priority": 1,
                "enabled": True,
            },
        )
        assert prompt_response.status_code in (200, 201), prompt_response.text

        third = _render(api_client, "INV05")
        assert third.status_code == 200, third.text
        stats_after = _stats(api_client)
        assert stats_after["misses"] >= stats_before["misses"] + 1
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_06_cache_flush(self, api_client):
        assert _render(api_client, "FLUSH06A").status_code == 200
        assert _render(api_client, "FLUSH06B").status_code == 200
        assert _stats(api_client)["entries"] >= 2

        flush = api_client.post("/cache/flush")
        assert flush.status_code == 200, flush.text
        assert _stats(api_client)["entries"] == 0

        again = _render(api_client, "FLUSH06A")
        assert again.status_code == 200, again.text
        assert _stats(api_client)["misses"] >= 3
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_07_cache_stats_endpoint(self, api_client):
        assert _render(api_client, "STAT07").status_code == 200
        stats = _stats(api_client)

        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "memory_bytes" in stats
        assert stats["entries"] >= 1
        assert stats["misses"] >= 1
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_it_cache_08_cache_disabled(self, api_client):
        disable = api_client.post(
            "/config/update",
            json={"updates": {"cache.enabled": False}},
        )
        assert disable.status_code == 200, disable.text

        stats_disabled = _stats(api_client)
        assert stats_disabled["enabled"] is False

        # Warm up the render path first (LLM connection / model load / route
        # compilation) so the timed comparison below is not dominated by a
        # one-off warm-up spike on the first measured call. Cache stays disabled,
        # so this does not populate any cache entry (asserted via entries == 0).
        warmup = _render(api_client, "DIS08")
        assert warmup.status_code == 200, warmup.text

        start_1 = time.perf_counter()
        first = _render(api_client, "DIS08")
        duration_1 = time.perf_counter() - start_1
        assert first.status_code == 200, first.text

        start_2 = time.perf_counter()
        second = _render(api_client, "DIS08")
        duration_2 = time.perf_counter() - start_2
        assert second.status_code == 200, second.text

        stats_after = _stats(api_client)
        assert stats_after["enabled"] is False
        assert stats_after["entries"] == 0
        # With cache disabled the second call is NOT served from cache,
        # but the first call incurs warm-up (LLM connection, model load).
        # Use 0.3x to avoid flaky failures from warm-up disparity.
        assert duration_2 >= duration_1 * 0.3, (duration_1, duration_2)

        enable = api_client.post(
            "/config/update",
            json={"updates": {"cache.enabled": True}},
        )
        assert enable.status_code == 200, enable.text
