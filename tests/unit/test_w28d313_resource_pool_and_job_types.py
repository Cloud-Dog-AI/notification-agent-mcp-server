"""W28D-313: PS-95 resource pool adoption and package pin validation."""

import importlib
import importlib.metadata

import pytest


class TestPackagePins:
    """Verify W28D-311 package version pins are installed."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_cloud_dog_jobs_version(self):
        version = importlib.metadata.version("cloud_dog_jobs")
        assert version.startswith("0.4"), f"Expected cloud_dog_jobs 0.4.x, got {version}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_cloud_dog_api_kit_version(self):
        version = importlib.metadata.version("cloud_dog_api_kit")
        assert version.startswith("0.13"), f"Expected cloud_dog_api_kit 0.13.x, got {version}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_cloud_dog_llm_version(self):
        version = importlib.metadata.version("cloud_dog_llm")
        assert version.startswith("0.3"), f"Expected cloud_dog_llm 0.3.x, got {version}"


class TestJobRequestResourcePool:
    """Verify delivery jobs declare LLM resource pool requirement."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_job_request_accepts_resources_kwarg(self):
        from cloud_dog_jobs import JobRequest

        req = JobRequest(
            job_type="delivery",
            queue_name="test",
            payload={"delivery_id": 1},
            resources={"llm-pool": 1},
        )
        assert req.resources == {"llm-pool": 1}
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_delivery_job_declares_llm_pool(self):
        """The enqueue_delivery_job path must set resources={'llm-pool': 1}."""
        import inspect
        import textwrap
        from src.core.jobs.runtime import JobsRuntime

        source = inspect.getsource(JobsRuntime.enqueue_delivery_job)
        assert "resources=" in source, "enqueue_delivery_job must pass resources= to JobRequest"
        assert "llm-pool" in source, "enqueue_delivery_job must declare llm-pool resource"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_empty_resources_default(self):
        from cloud_dog_jobs import JobRequest

        req = JobRequest(job_type="test", queue_name="test")
        assert req.resources == {} or req.resources is not None


class TestDefaultsYamlResourcePools:
    """Verify defaults.yaml declares PS-95 resource pools."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_resource_pools_in_defaults(self):
        import yaml
        from pathlib import Path

        defaults_path = Path(__file__).resolve().parents[2] / "defaults.yaml"
        with open(defaults_path) as f:
            cfg = yaml.safe_load(f)
        pools = cfg.get("resource_pools", {})
        assert "llm-pool" in pools, "defaults.yaml must declare llm-pool"
        assert "delivery-pool" in pools, "defaults.yaml must declare delivery-pool"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_sync_budget_in_defaults(self):
        import yaml
        from pathlib import Path

        defaults_path = Path(__file__).resolve().parents[2] / "defaults.yaml"
        with open(defaults_path) as f:
            cfg = yaml.safe_load(f)
        mcp = cfg.get("mcp_server", {})
        assert "sync_budget_seconds" in mcp, "mcp_server must declare sync_budget_seconds"
        assert int(mcp["sync_budget_seconds"]) > 0
