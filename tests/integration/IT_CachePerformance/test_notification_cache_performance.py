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

"""Integration Test: W28A-413-C cache performance proof for notification-agent."""

from __future__ import annotations

import time

import pytest

from tests.utils.api_tracking import build_tracked_client


pytestmark = [pytest.mark.integration, pytest.mark.cache]


@pytest.fixture
def api_client(api_base_url, api_key, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=60.0,
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
    }


def _render(client, payload: dict[str, object]):
    return client.post("/api/v1/messages/render", json=payload)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_cold_vs_hot_single_call(api_client):
    """Prove cache hit is significantly faster than cache miss."""
    api_client.post("/cache/flush")

    payload = {
        "template": "Hello {name}, your order {order_id} is ready.",
        "variables": {"name": "Test User", "order_id": "ORD-001"},
        "language": "en",
        "channel_type": "email",
    }

    t1 = time.time()
    r1 = _render(api_client, payload)
    cold_time = time.time() - t1
    assert r1.status_code == 200, r1.text

    t2 = time.time()
    r2 = _render(api_client, payload)
    hot_time = time.time() - t2
    assert r2.status_code == 200, r2.text

    assert r1.json() == r2.json(), "Cache hit must return identical result"

    speedup = cold_time / hot_time if hot_time > 0 else float("inf")
    print(f"Cold: {cold_time:.3f}s, Hot: {hot_time:.3f}s, Speedup: {speedup:.1f}x")
    assert hot_time < cold_time * 0.5, (
        f"Cache hit ({hot_time:.3f}s) must be at least 2x faster than miss ({cold_time:.3f}s)"
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_batch_speedup_10_calls(api_client):
    """Prove 10 repeated calls are dramatically faster with cache."""
    api_client.post("/cache/flush")

    payload = {
        "template": "Dear {name}, reminder about {event}.",
        "variables": {"name": "Batch User", "event": "Meeting"},
        "language": "en",
        "channel_type": "email",
    }

    t_cold = time.time()
    cold = _render(api_client, payload)
    cold_time = time.time() - t_cold
    assert cold.status_code == 200, cold.text

    t_hot = time.time()
    for _ in range(10):
        response = _render(api_client, payload)
        assert response.status_code == 200, response.text
    hot_total = time.time() - t_hot

    hot_avg = hot_total / 10
    speedup = cold_time / hot_avg if hot_avg > 0 else float("inf")
    print(f"Cold: {cold_time:.3f}s, Hot avg (10 calls): {hot_avg:.3f}s, Speedup: {speedup:.1f}x")
    assert hot_avg < cold_time * 0.5, (
        f"Average cached call ({hot_avg:.3f}s) must be at least 2x faster than cold call ({cold_time:.3f}s)"
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_stats_show_hit_rate(api_client):
    """Prove cache stats accurately reflect hit/miss ratio."""
    api_client.post("/cache/flush")

    payload = {
        "template": "Test {x}",
        "variables": {"x": "1"},
        "language": "en",
        "channel_type": "email",
    }

    _render(api_client, payload)
    for _ in range(5):
        response = _render(api_client, payload)
        assert response.status_code == 200, response.text

    stats = _stats(api_client)
    print(f"Stats: {stats}")

    assert stats["hits"] >= 5, f"Expected >=5 hits, got {stats['hits']}"
    assert stats["misses"] >= 1, f"Expected >=1 miss, got {stats['misses']}"

    hit_rate = stats["hits"] / (stats["hits"] + stats["misses"])
    print(f"Hit rate: {hit_rate:.0%}")
    assert hit_rate >= 0.8, f"Hit rate should be >=80%, got {hit_rate:.0%}"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_different_params_not_cached(api_client):
    """Prove different inputs produce cache misses."""
    api_client.post("/cache/flush")

    for i in range(5):
        response = _render(
            api_client,
            {
                "template": f"Message {{n}} variant {i}",
                "variables": {"n": str(i)},
                "language": "en",
                "channel_type": "email",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json().get("rendered_text")

    stats = _stats(api_client)
    assert stats["misses"] >= 5, f"5 unique calls should be 5 misses, got {stats['misses']}"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_invalidation_resets_speed(api_client):
    """Prove invalidation forces a slow re-computation."""
    payload = {
        "template": "Invalidate test {x}",
        "variables": {"x": "1"},
        "language": "en",
        "channel_type": "email",
    }

    warm = _render(api_client, payload)
    assert warm.status_code == 200, warm.text

    t1 = time.time()
    cached = _render(api_client, payload)
    cached_time = time.time() - t1
    assert cached.status_code == 200, cached.text

    flush = api_client.post("/cache/flush")
    assert flush.status_code == 200, flush.text

    t2 = time.time()
    recompute = _render(api_client, payload)
    recompute_time = time.time() - t2
    assert recompute.status_code == 200, recompute.text

    print(f"Cached: {cached_time:.3f}s, After invalidation: {recompute_time:.3f}s")
    assert recompute_time > cached_time * 1.5, (
        f"After invalidation ({recompute_time:.3f}s) should be slower than cached ({cached_time:.3f}s)"
    )
