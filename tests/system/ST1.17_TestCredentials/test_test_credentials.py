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
System Test ST1.17: Test Credentials Verification

Verifies that:
1. Environment file (--env private/env-test) loads correctly
2. SMTP credentials are configured
3. Slack webhook credentials are configured
4. API server credentials are configured
5. All required credentials for Application/Business Tests are present

Related Requirements: NF1.5 (Portability), NF1.6 (Testability)
Related Tasks: T36, T37
"""

import pytest
from tests.utils.test_helpers import check_test_dependencies
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config
from src.config import RuntimeConfig


class TestTestCredentials:
    """Verify test credentials are loaded from env file"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-016")
    
    def test_env_file_loaded(self, pytestconfig):
        """Verify environment variables are loaded from env file"""
        print("\n" + "="*80)
        print("TEST CREDENTIALS VERIFICATION")
        print("="*80 + "\n")
        
        # Check if we're using the test env file
        env_file = pytestconfig.getoption("--env")
        if not env_file:
            pytest.fail("❌ CRITICAL: --env file parameter is REQUIRED for all tests")
        print(f"Environment file: {env_file}")
        
        # Load config with explicit env file
        config = RuntimeConfig(env_file=env_file, load_env_file=True)
        print(f"✓ Config loaded successfully")
        
        return config
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-016")
    
    def test_smtp_credentials_configured(self, pytestconfig):
        """Verify SMTP credentials are configured"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_smtp_credentials_configured"
        )

        print("\n" + "-"*80)
        print("SMTP CREDENTIALS CHECK")
        print("-"*80)
        
        env_file = pytestconfig.getoption("--env")
        if not env_file:
            pytest.fail("❌ CRITICAL: --env file parameter is REQUIRED for all tests")
        config = RuntimeConfig(env_file=env_file, load_env_file=True)
        
        # Check SMTP channel configuration
        channels = config.get("channels", {})
        smtp_config = channels.get("smtp", {}).get("default", {})
        
        required = ["host", "port", "username", "password", "from_address"]
        missing = []
        present = []
        
        for key in required:
            value = smtp_config.get(key)
            if value:
                # Mask sensitive values
                if key == "password":
                    display_value = "*" * len(str(value))
                else:
                    display_value = value
                print(f"  ✓ {key}: {display_value}")
                present.append(key)
            else:
                print(f"  ✗ {key}: MISSING")
                missing.append(key)
        
        # Also check environment variables directly
        print("\n  Environment Variables:")
        env_vars = {
            "CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__HOST": os.environ.get("CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__HOST"),
            "CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__PORT": os.environ.get("CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__PORT"),
            "CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__USERNAME": os.environ.get("CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__USERNAME"),
            "CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__PASSWORD": os.environ.get("CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__PASSWORD"),
            "CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__FROM_ADDRESS": os.environ.get("CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__FROM_ADDRESS"),
        }
        
        for key, value in env_vars.items():
            if value:
                display_value = "*" * len(str(value)) if "PASSWORD" in key else value
                print(f"    ✓ {key}: {display_value}")
            else:
                print(f"    ✗ {key}: MISSING")
        
        if missing:
            pytest.skip(f"SMTP credentials missing: {', '.join(missing)}. Load env file with --env <env-file>")
        
        print(f"\n  ✓ All SMTP credentials configured ({len(present)}/{len(required)})")
        return smtp_config
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-016")
    
    def test_slack_credentials_configured(self, pytestconfig):
        """Verify Slack webhook credentials are configured"""
        print("\n" + "-"*80)
        print("SLACK WEBHOOK CREDENTIALS CHECK")
        print("-"*80)
        
        env_file = pytestconfig.getoption("--env")
        if not env_file:
            pytest.fail("❌ CRITICAL: --env file parameter is REQUIRED for all tests")
        config = RuntimeConfig(env_file=env_file, load_env_file=True)
        
        # Check Slack channel configuration
        channels = config.get("channels", {})
        chat_config = channels.get("chat_rest", {}).get("transparentbordes", {})
        
        required = ["endpoint"]
        missing = []
        present = []
        
        for key in required:
            value = chat_config.get(key)
            if value:
                # Mask webhook URL partially
                if key == "endpoint":
                    display_value = str(value)[:50] + "..." + str(value)[-10:]
                else:
                    display_value = value
                print(f"  ✓ {key}: {display_value}")
                present.append(key)
            else:
                print(f"  ✗ {key}: MISSING")
                missing.append(key)
        
        # Also check environment variables directly
        print("\n  Environment Variables:")
        env_var = "CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__ENDPOINT"
        env_value = os.environ.get(env_var)
        if env_value:
            display_value = env_value[:50] + "..." + env_value[-10:] if len(env_value) > 60 else env_value
            print(f"    ✓ {env_var}: {display_value}")
        else:
            print(f"    ✗ {env_var}: MISSING")
        
        if missing:
            pytest.skip(f"Slack credentials missing: {', '.join(missing)}. Load env file with --env <env-file>")
        
        print(f"\n  ✓ All Slack credentials configured ({len(present)}/{len(required)})")
        return chat_config
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-016")
    
    def test_api_credentials_configured(self, pytestconfig):
        """Verify API server credentials are configured"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_api_credentials_configured"
        )

        print("\n" + "-"*80)
        print("API SERVER CREDENTIALS CHECK")
        print("-"*80)
        
        env_file = pytestconfig.getoption("--env")
        if not env_file:
            pytest.fail("❌ CRITICAL: --env file parameter is REQUIRED for all tests")
        config = RuntimeConfig(env_file=env_file, load_env_file=True)
        
        # Check API server configuration
        api_config = config.get("api_server", {})
        
        required = ["api_key", "base_url"]
        missing = []
        present = []
        
        for key in required:
            value = api_config.get(key)
            if value:
                # Mask API key
                if key == "api_key":
                    display_value = "*" * len(str(value))
                else:
                    display_value = value
                print(f"  ✓ {key}: {display_value}")
                present.append(key)
            else:
                print(f"  ✗ {key}: MISSING")
                missing.append(key)
        
        # Also check environment variables directly
        print("\n  Environment Variables:")
        env_vars = {
            "CLOUD_DOG__NOTIFY__API_SERVER__API_KEY": os.environ.get("CLOUD_DOG__NOTIFY__API_SERVER__API_KEY"),
            "CLOUD_DOG__NOTIFY__API_SERVER__BASE_URL": os.environ.get("CLOUD_DOG__NOTIFY__API_SERVER__BASE_URL"),
        }
        
        for key, value in env_vars.items():
            if value:
                display_value = "*" * len(str(value)) if "API_KEY" in key else value
                print(f"    ✓ {key}: {display_value}")
            else:
                print(f"    ✗ {key}: MISSING")
        
        if missing:
            pytest.skip(f"API credentials missing: {', '.join(missing)}. Load env file with --env <env-file>")
        
        print(f"\n  ✓ All API credentials configured ({len(present)}/{len(required)})")
        return api_config
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-016")
    
    def test_all_test_credentials_summary(self, pytestconfig):
        """Summary of all test credentials status"""
        print("\n" + "="*80)
        print("TEST CREDENTIALS SUMMARY")
        print("="*80 + "\n")
        
        env_file = pytestconfig.getoption("--env")
        if not env_file:
            pytest.fail("❌ CRITICAL: --env file parameter is REQUIRED for all tests")
        config = RuntimeConfig(env_file=env_file, load_env_file=True)
        
        # SMTP
        smtp_config = config.get("channels", {}).get("smtp", {}).get("default", {})
        smtp_ok = all(smtp_config.get(k) for k in ["host", "port", "username", "password", "from_address"])
        
        # Slack
        slack_config = config.get("channels", {}).get("chat_rest", {}).get("transparentbordes", {})
        slack_ok = bool(slack_config.get("endpoint"))
        
        # API
        api_config = config.get("api_server", {})
        api_ok = all(api_config.get(k) for k in ["api_key", "base_url"])
        
        print(f"SMTP Credentials:     {'✓ CONFIGURED' if smtp_ok else '✗ MISSING'}")
        print(f"Slack Webhook:         {'✓ CONFIGURED' if slack_ok else '✗ MISSING'}")
        print(f"API Server:            {'✓ CONFIGURED' if api_ok else '✗ MISSING'}")
        
        all_ok = smtp_ok and slack_ok and api_ok
        
        if all_ok:
            print("\n✅ All test credentials are configured and ready for Application/Business Tests")
        else:
            print("\n⚠️  Some credentials are missing. Load env file with --env <env-file>")
            missing_list = []
            if not smtp_ok:
                missing_list.append("SMTP")
            if not slack_ok:
                missing_list.append("Slack")
            if not api_ok:
                missing_list.append("API")
            print(f"   Missing: {', '.join(missing_list)}")
        
        return {
            "smtp": smtp_ok,
            "slack": slack_ok,
            "api": api_ok,
            "all": all_ok
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

