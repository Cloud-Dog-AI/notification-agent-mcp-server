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
Unit tests for Configuration System

Tests:
- Configuration loading hierarchy
- Environment variable parsing
- Secret masking
- Required field validation
"""

import os
import pytest
import tempfile
from pathlib import Path

from src.config import RuntimeConfig


pytestmark = [pytest.mark.unit, pytest.mark.no_runtime_dependency]


class TestRuntimeConfig:
    """Test RuntimeConfig class"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("CS-001")
    
    def test_load_from_default_yaml(self):
        """Test loading from defaults.yaml"""
        # Use the actual defaults.yaml
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        assert config.config is not None
        assert "app" in config.config
        assert config.get("app.version") == config.config["app"]["version"]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("CS-005")
    
    def test_get_with_dot_notation(self):
        """Test getting values with dot notation"""
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        # Test nested access
        port = config.get("api_server.port")
        assert port == config.config["api_server"]["port"]
        
        # Test default value
        assert config.get("nonexistent.key", "default") == "default"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("CS-006")
    
    def test_set_with_dot_notation(self):
        """Test setting values with dot notation"""
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        config.set("api_server.port", 9999)
        assert config.get("api_server.port") == 9999
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("CS-007")
    
    def test_env_var_override(self, tmp_path, monkeypatch):
        """Test env file override (RULES-compliant; no direct os.environ)"""
        # Clear session-level env var so the test's env file takes precedence
        monkeypatch.delenv("CLOUD_DOG__NOTIFY__API_SERVER__PORT", raising=False)
        env_path = tmp_path / "env-test"
        env_path.write_text("CLOUD_DOG__NOTIFY__API_SERVER__PORT=7777\n")

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("api_server.port") == 7777
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_secret_masking(self):
        """Test that secrets are masked"""
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        # Create test data with secrets
        test_data = {
            "api_key": "secret123",
            "password": "mypassword",
            "normal_field": "visible",
            "nested": {
                "token": "secrettoken",
                "public": "public_value"
            }
        }
        
        masked = config.mask_secrets(test_data)
        
        assert masked["api_key"] == "***REDACTED***"
        assert masked["password"] == "***REDACTED***"
        assert masked["normal_field"] == "visible"
        assert masked["nested"]["token"] == "***REDACTED***"
        assert masked["nested"]["public"] == "public_value"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_required_fields_validation(self):
        """Test required field validation"""
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        # These are empty in defaults.yaml and should be reported as missing
        missing = config.validate_required([
            "app.version",
            "api_server.port",
        ])
        expected_missing = {key for key in ["app.version", "api_server.port"] if not config.get(key)}
        assert set(missing) == expected_missing
        
        # This should be missing
        missing = config.validate_required([
            "nonexistent.field",
        ])
        assert len(missing) == 1
        assert "nonexistent.field" in missing
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_config_precedence_env_over_config(self, tmp_path, monkeypatch):
        """Test env file takes precedence over config.yaml and defaults.yaml"""
        monkeypatch.delenv("CLOUD_DOG__NOTIFY__API_SERVER__PORT", raising=False)
        env_path = tmp_path / "env-precedence"
        env_path.write_text("CLOUD_DOG__NOTIFY__API_SERVER__PORT=9001\n")

        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text("api_server:\n  port: 9000\n")

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml=str(config_yaml),
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("api_server.port") == 9001
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_boolean_values(self):
        """Test parsing boolean environment variables"""
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        # Test various boolean formats
        assert config._parse_value("true") == True
        assert config._parse_value("True") == True
        assert config._parse_value("1") == True
        assert config._parse_value("yes") == True
        assert config._parse_value("false") == False
        assert config._parse_value("False") == False
        assert config._parse_value("0") == False
        assert config._parse_value("no") == False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_numeric_values(self):
        """Test parsing numeric environment variables"""
        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file="nonexistent",
            load_env_file=False,
        )
        
        assert config._parse_value("123") == 123
        assert config._parse_value("123.45") == 123.45
        assert config._parse_value("not_a_number") == "not_a_number"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_s3_aliases_from_access_key_id_are_normalized(self, tmp_path):
        """S3 access_key_id/secret_access_key should hydrate canonical access_key/secret_key."""
        env_path = tmp_path / "env-s3-alias-forward"
        env_path.write_text(
            "\n".join(
                [
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__ENDPOINT=https://storage.example.com",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__BUCKET=test",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__ACCESS_KEY_ID=minio",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__SECRET_ACCESS_KEY=minio123",
                ]
            )
            + "\n"
        )

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("storage.s3.access_key") == "minio"
        assert config.get("storage.s3.secret_key") == "minio123"
        assert config.get("storage.s3.access_key_id") == "minio"
        assert config.get("storage.s3.secret_access_key") == "minio123"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_s3_aliases_from_access_key_are_normalized(self, tmp_path):
        """S3 access_key/secret_key should hydrate access_key_id/secret_access_key aliases."""
        env_path = tmp_path / "env-s3-alias-reverse"
        env_path.write_text(
            "\n".join(
                [
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__ENDPOINT=https://storage.example.com",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__BUCKET=test",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__ACCESS_KEY=minio",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__SECRET_KEY=minio123",
                ]
            )
            + "\n"
        )

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("storage.s3.access_key") == "minio"
        assert config.get("storage.s3.secret_key") == "minio123"
        assert config.get("storage.s3.access_key_id") == "minio"
        assert config.get("storage.s3.secret_access_key") == "minio123"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_s3_endpoint_and_bucket_aliases_are_normalized(self, tmp_path, monkeypatch):
        """S3 url/bucket_name aliases should hydrate endpoint/bucket canonicals."""
        for key in list(os.environ):
            if key.startswith("CLOUD_DOG__NOTIFY__STORAGE__S3__"):
                monkeypatch.delenv(key, raising=False)
        env_path = tmp_path / "env-s3-endpoint-bucket-alias"
        env_path.write_text(
            "\n".join(
                [
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__URL=https://storage.example.com",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__BUCKET_NAME=test",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__ACCESS_KEY_ID=minio",
                    "CLOUD_DOG__NOTIFY__STORAGE__S3__SECRET_ACCESS_KEY=minio123",
                ]
            )
            + "\n"
        )

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("storage.s3.endpoint") == "https://storage.example.com"
        assert config.get("storage.s3.url") == "https://storage.example.com"
        assert config.get("storage.s3.bucket") == "test"
        assert config.get("storage.s3.bucket_name") == "test"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_webdav_aliases_are_normalized(self, tmp_path):
        """WebDAV endpoint/user/pass aliases should hydrate url/username/password."""
        env_path = tmp_path / "env-webdav-aliases"
        env_path.write_text(
            "\n".join(
                [
                    "CLOUD_DOG__NOTIFY__STORAGE__WEBDAV__ENDPOINT=https://files.example.com/remote.php/dav/files/user/temp",
                    "CLOUD_DOG__NOTIFY__STORAGE__WEBDAV__USER=gary",
                    "CLOUD_DOG__NOTIFY__STORAGE__WEBDAV__PASS=secret",
                ]
            )
            + "\n"
        )

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("storage.webdav.url") == "https://files.example.com/remote.php/dav/files/user/temp"
        assert config.get("storage.webdav.endpoint") == "https://files.example.com/remote.php/dav/files/user/temp"
        assert config.get("storage.webdav.username") == "gary"
        assert config.get("storage.webdav.user") == "gary"
        assert config.get("storage.webdav.password") == "secret"
        assert config.get("storage.webdav.pass") == "secret"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_ftp_aliases_are_normalized(self, tmp_path):
        """FTP server/user/pass aliases should hydrate host/username/password canonicals."""
        env_path = tmp_path / "env-ftp-aliases"
        env_path.write_text(
            "\n".join(
                [
                    "CLOUD_DOG__NOTIFY__STORAGE__FTP__SERVER=ftp.example.com",
                    "CLOUD_DOG__NOTIFY__STORAGE__FTP__FTP_PORT=21",
                    "CLOUD_DOG__NOTIFY__STORAGE__FTP__USER=mcptest",
                    "CLOUD_DOG__NOTIFY__STORAGE__FTP__PASS=mcppassword",
                    "CLOUD_DOG__NOTIFY__STORAGE__FTP__PASSIVE=true",
                ]
            )
            + "\n"
        )

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("storage.ftp.host") == "ftp.example.com"
        assert config.get("storage.ftp.server") == "ftp.example.com"
        assert str(config.get("storage.ftp.port")) == "21"
        assert str(config.get("storage.ftp.ftp_port")) == "21"
        assert config.get("storage.ftp.username") == "mcptest"
        assert config.get("storage.ftp.user") == "mcptest"
        assert config.get("storage.ftp.password") == "mcppassword"
        assert config.get("storage.ftp.pass") == "mcppassword"
        assert str(config.get("storage.ftp.passive_mode")).lower() == "true"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_file_channel_s3_aliases_are_normalized(self, tmp_path, monkeypatch):
        """file_channel.s3 should normalize legacy alias keys exactly like storage.s3."""
        for key in list(os.environ):
            if key.startswith("CLOUD_DOG__NOTIFY__FILE_CHANNEL__S3__"):
                monkeypatch.delenv(key, raising=False)
        env_path = tmp_path / "env-file-channel-s3-aliases"
        env_path.write_text(
            "\n".join(
                [
                    "CLOUD_DOG__NOTIFY__FILE_CHANNEL__S3__URL=https://storage.example.com",
                    "CLOUD_DOG__NOTIFY__FILE_CHANNEL__S3__BUCKET_NAME=test",
                    "CLOUD_DOG__NOTIFY__FILE_CHANNEL__S3__ACCESS_KEY_ID=minio",
                    "CLOUD_DOG__NOTIFY__FILE_CHANNEL__S3__SECRET_ACCESS_KEY=minio123",
                ]
            )
            + "\n"
        )

        config = RuntimeConfig(
            default_yaml="defaults.yaml",
            config_yaml="nonexistent.yaml",
            env_file=str(env_path),
            load_env_file=True,
        )

        assert config.get("file_channel.s3.endpoint") == "https://storage.example.com"
        assert config.get("file_channel.s3.bucket") == "test"
        assert config.get("file_channel.s3.access_key") == "minio"
        assert config.get("file_channel.s3.secret_key") == "minio123"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_get_config_singleton():
    """Test that get_config returns singleton"""
    from src.config import get_config
    
    config1 = get_config(force_reload=True)
    config2 = get_config()
    
    assert config1 is config2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]
