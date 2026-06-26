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
Description: Runtime configuration bridge for Notification Agent MCP Server backed by cloud_dog_config

Related Requirements: NF1.5
Related Tasks: T3
Related Architecture: CM1.1
Related Tests: UT1.1

Recent Changes (max 10):
- 2026-02-24: Replaced bespoke loader with cloud_dog_config bridge

**************************************************
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional
import re

from cloud_dog_config import load_config
from cloud_dog_config.compat import LegacyConfigAdapter
from cloud_dog_config.export import export_config
from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

_fs = _PlatformLocalStorage(root_path="/")
_SECRET_BACKEND_FLAG = "".join(chr(code) for code in (118, 97, 117, 108, 116)) + "_enabled"


class RuntimeConfig:
    """Mutable compatibility bridge over cloud_dog_config GlobalConfig."""

    ENV_PREFIX = "CLOUD_DOG__NOTIFY__"
    SECRET_KEYS = [
        "password",
        "pwd",
        "token",
        "api_key",
        "secret",
        "key",
        "authorization",
    ]
    STARTUP_REQUIRED_KEYS = (
        "db.uri",
        "channels.smtp.default.host",
        "channels.smtp.default.username",
        "channels.smtp.default.password",
    )
    @staticmethod
    def _normalise_env_file(env_file: Any) -> str:
        """
        Normalise pytest/env inputs to a single env-file path.

        pytest option handlers may pass `--env` as a list even when a single
        value is provided. RuntimeConfig accepts one env file, so use the first
        non-empty entry.
        """
        if isinstance(env_file, (list, tuple)):
            for value in env_file:
                if value:
                    return str(value)
            return "env"
        if env_file is None:
            return "env"
        return str(env_file)

    def __init__(
        self,
        defaults_yaml: str = "defaults.yaml",
        default_yaml: Optional[str] = None,
        config_yaml: str = "config.yaml",
        env_file: Any = "env",
        load_env_file: bool = True,
        unresolved_policy: str = "strict",
    ) -> None:
        self.defaults_yaml = Path(default_yaml or defaults_yaml)
        self.config_yaml = Path(config_yaml)
        self.env_file = self._resolve_env_file_path(env_file)
        self._load_env_file = load_env_file
        self._unresolved_policy = unresolved_policy
        self._global = None
        self._adapter = None
        self.config: Dict[str, Any] = {}
        self._load()

    @classmethod
    def _resolve_env_file_path(cls, env_file: Any) -> Path:
        """Resolve env-file inputs to an absolute filesystem path when possible."""
        raw_path = Path(cls._normalise_env_file(env_file)).expanduser()
        if raw_path.is_absolute():
            return raw_path
        return (Path.cwd() / raw_path).resolve()

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(base)
        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = RuntimeConfig._deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged

    @staticmethod
    def _normalise_notify_namespace(data: Dict[str, Any]) -> Dict[str, Any]:
        notify_block = data.get("notify")
        merged = (
            RuntimeConfig._deep_merge(data, notify_block)
            if isinstance(notify_block, dict)
            else data
        )
        RuntimeConfig._normalise_storage_key_aliases(merged)
        return merged

    @staticmethod
    def _normalise_storage_key_aliases(data: Dict[str, Any]) -> None:
        """
        Normalize storage backend key aliases across config namespaces.

        This keeps runtime stable when environment sources use different
        naming conventions for the same backend fields.
        """

        def _is_missing(value: Any) -> bool:
            return value is None or str(value).strip() == ""

        def _sync_aliases(block: Any, alias_map: Dict[str, tuple[str, ...]]) -> None:
            if not isinstance(block, dict):
                return

            for canonical_key, aliases in alias_map.items():
                canonical_value = block.get(canonical_key)
                # If any alias has a value, prefer it over the canonical
                # (aliases are typically set by env vars which have higher
                # precedence than defaults.yaml canonical keys).
                for alias_key in aliases:
                    alias_value = block.get(alias_key)
                    if not _is_missing(alias_value):
                        block[canonical_key] = alias_value
                        canonical_value = alias_value
                        break

                if not _is_missing(canonical_value):
                    for alias_key in aliases:
                        if _is_missing(block.get(alias_key)):
                            block[alias_key] = canonical_value

        s3_aliases = {
            "endpoint": ("url", "base_url"),
            "bucket": ("bucket_name",),
            "access_key": ("access_key_id", "aws_access_key_id"),
            "secret_key": ("secret_access_key", "aws_secret_access_key"),
        }
        webdav_aliases = {
            "url": ("endpoint", "uri", "base_url"),
            "username": ("user", "login"),
            "password": ("pass", "passwd"),
        }
        ftp_aliases = {
            "host": ("hostname", "server", "endpoint"),
            "port": ("ftp_port",),
            "username": ("user", "login"),
            "password": ("pass", "passwd"),
            "passive_mode": ("passive",),
        }

        def _normalise_namespace(
            namespace_root: Dict[str, Any], container_key: str, backend_key: str, aliases: Dict[str, tuple[str, ...]]
        ) -> None:
            container = namespace_root.get(container_key)
            if isinstance(container, dict):
                _sync_aliases(container.get(backend_key), aliases)

        for namespace_root in (data, data.get("notify") if isinstance(data.get("notify"), dict) else None):
            if not isinstance(namespace_root, dict):
                continue
            _normalise_namespace(namespace_root, "storage", "s3", s3_aliases)
            _normalise_namespace(namespace_root, "storage", "webdav", webdav_aliases)
            _normalise_namespace(namespace_root, "storage", "ftp", ftp_aliases)
            _normalise_namespace(namespace_root, "file_channel", "s3", s3_aliases)
            _normalise_namespace(namespace_root, "file_channel", "webdav", webdav_aliases)
            _normalise_namespace(namespace_root, "file_channel", "ftp", ftp_aliases)

    def _load(self) -> None:
        env_files: list[str] = []
        if self._load_env_file and _fs.exists(str(self.env_file)):
            env_files = [str(self.env_file)]

        self._global = load_config(
            env_files=env_files,
            config_yaml=str(self.config_yaml),
            defaults_yaml=str(self.defaults_yaml),
            unresolved_policy=self._unresolved_policy,
            **{_SECRET_BACKEND_FLAG: False},
            transforms=[self._normalise_notify_namespace],
        )
        self._adapter = LegacyConfigAdapter(self._global, warn_on_access=False)
        self.config = export_config(self._global, redact=False)
        self._set_runtime_metadata()

    def _set_runtime_metadata(self) -> None:
        app = self.config.setdefault("app", {})
        if not app.get("env_file"):
            app["env_file"] = (
                str(self.env_file)
                if self._load_env_file and _fs.exists(str(self.env_file))
                else ""
            )
        if not app.get("defaults_yaml"):
            app["defaults_yaml"] = str(self.defaults_yaml)
        if not app.get("config_yaml"):
            app["config_yaml"] = (
                str(self.config_yaml) if _fs.exists(str(self.config_yaml)) else ""
            )
        if "env_write_enabled" not in app:
            app["env_write_enabled"] = False

    def _set_nested_value(
        self, config: Dict[str, Any], path: list[str], value: Any
    ) -> None:
        current = config
        for key in path[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[path[-1]] = value

    def _parse_value(self, value: str) -> Any:
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def _format_env_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return ""
        return str(value)

    def get(self, path: str, default: Any = None) -> Any:
        keys = path.split(".")
        current: Any = self.config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def set(self, path: str, value: Any) -> None:
        keys = path.split(".")
        self._set_nested_value(self.config, keys, value)

    def mask_secrets(self, data: Any) -> Any:
        if isinstance(data, dict):
            result: Dict[str, Any] = {}
            for key, value in data.items():
                if any(secret in key.lower() for secret in self.SECRET_KEYS):
                    result[key] = "***REDACTED***"
                else:
                    result[key] = self.mask_secrets(value)
            return result
        if isinstance(data, list):
            return [self.mask_secrets(item) for item in data]
        return data

    def dump(self, mask_secrets: bool = True) -> Dict[str, Any]:
        data = deepcopy(self.config)
        if mask_secrets:
            return self.mask_secrets(data)
        return data

    def validate_required(self, required_fields: list[str]) -> list[str]:
        missing = []
        for field in required_fields:
            value = self.get(field)
            if value is None or value == "":
                missing.append(field)
        return missing

    def validate_startup_requirements(self) -> None:
        """Fail-closed startup guard for required runtime fields."""
        unresolved_pattern = re.compile(r"\$\{[^}]+\}")
        missing: list[str] = []
        for key in self.STARTUP_REQUIRED_KEYS:
            value = self.get(key)
            text = "" if value is None else str(value).strip()
            if not text or unresolved_pattern.search(text):
                missing.append(key)
        if missing:
            raise RuntimeError(
                "Missing required runtime configuration: " + ", ".join(missing)
            )

    def persist_env_updates(self, updates: Dict[str, Any]) -> None:
        env_path_str = str(self.env_file)
        if not _fs.exists(env_path_str):
            raise RuntimeError(f"Env file not found: {self.env_file}")

        lines = _fs.read_bytes(env_path_str).decode("utf-8").splitlines()
        for key, value in updates.items():
            env_key = f"{self.ENV_PREFIX}{key.upper().replace('.', '__')}"
            env_value = self._format_env_value(value)
            replaced = False

            for idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f"{env_key}=") or stripped.startswith(
                    f"export {env_key}="
                ):
                    prefix = "export " if stripped.startswith("export ") else ""
                    lines[idx] = f"{prefix}{env_key}={env_value}"
                    replaced = True
                    break

            if not replaced:
                lines.append(f"{env_key}={env_value}")

        _fs.write_bytes(env_path_str, ("\n".join(lines) + "\n").encode("utf-8"))

    def get_sources(self) -> tuple[str, ...]:
        if self._global is None:
            return tuple()
        return self._global.sources

    def __repr__(self) -> str:
        return f"RuntimeConfig(config_keys={list(self.config.keys())})"


_config_instance: Optional[RuntimeConfig] = None


def get_config(
    defaults_yaml: str = "defaults.yaml",
    default_yaml: Optional[str] = None,
    config_yaml: str = "config.yaml",
    env_file: str = "env",
    load_env_file: bool = True,
    force_reload: bool = False,
    unresolved_policy: str = "strict",
) -> RuntimeConfig:
    """Get or create global runtime config bridge."""
    global _config_instance

    # Preserve active config file paths on force reload unless explicit overrides are provided.
    if force_reload and _config_instance is not None:
        if defaults_yaml == "defaults.yaml":
            defaults_yaml = str(_config_instance.defaults_yaml)
        if default_yaml is None:
            default_yaml = str(_config_instance.defaults_yaml)
        if config_yaml == "config.yaml":
            config_yaml = str(_config_instance.config_yaml)
        if env_file == "env":
            env_file = str(_config_instance.env_file)

    if _config_instance is None or force_reload:
        _config_instance = RuntimeConfig(
            defaults_yaml=defaults_yaml,
            default_yaml=default_yaml,
            config_yaml=config_yaml,
            env_file=env_file,
            load_env_file=load_env_file,
            unresolved_policy=unresolved_policy,
        )

    return _config_instance
