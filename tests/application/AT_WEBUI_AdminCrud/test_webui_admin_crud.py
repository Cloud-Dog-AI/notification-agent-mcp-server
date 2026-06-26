#!/usr/bin/env python3

from __future__ import annotations

import time

import pytest

from tests.application.webui_e2e_support import (
    AdminApi,
    api_timeout_s,
    browser_fetch_json,
    login_via_browser,
    managed_page,
    normalize_localhost,
    page_timeout_ms,
    require_value,
    wait_until,
    wait_for_heading,
    wait_for_text,
)


pytestmark = [pytest.mark.application, pytest.mark.no_llm_dependency]
@pytest.mark.AT
@pytest.mark.webui
@pytest.mark.req("FR-023")


def test_webui_t1_t2_t4_t8_admin_login_user_crud_api_key_and_preferences(test_config, test_email_domain):
    base_url = normalize_localhost(require_value(test_config, "web_server.base_url").rstrip("/"))
    api_base_url = normalize_localhost(require_value(test_config, "api_server.base_url").rstrip("/"))
    api_key = require_value(test_config, "api_server.api_key")
    username = require_value(test_config, "web_server.username")
    password = require_value(test_config, "web_server.password")
    timeout_ms = page_timeout_ms(test_config)
    timeout_s = api_timeout_s(test_config)
    suffix = str(int(time.time()))
    created_user_id: int | None = None

    new_username = f"e2e_notify_user_{suffix}"
    new_email = f"{new_username}{test_email_domain}"
    edited_display_name = f"E2E Notify User {suffix}"
    key_prefix = f"e2e_test_key_{suffix}"

    with AdminApi(api_base_url, api_key, timeout_s) as api:
        try:
            with managed_page("w28a-442-admin-crud", timeout_ms) as page:
                login_via_browser(page, base_url, username, password, timeout_ms)
                page.get_by_role("link", name="Users").click()
                wait_for_heading(page, "Users", timeout_ms)
                assert page.context.cookies(), "Expected session cookie after login"

                page.get_by_role("button", name="Add user").click()
                page.fill("#users-dialog-username", new_username)
                page.fill("#users-dialog-email", new_email)
                page.fill("#users-dialog-display-name", "E2E Notify User")
                page.fill("#users-dialog-password", "Pw12345!")
                page.select_option("#users-dialog-role", "viewer")
                page.select_option("#users-dialog-language", "en")
                page.select_option("#users-dialog-preferred-channel", "email_default")
                page.select_option("#users-dialog-content-style", "html")
                page.get_by_role("button", name="Save changes").click()

                wait_for_text(page, f"Created user {new_username}.", timeout_ms)
                created_user_id = api.wait_for_user_id(new_username, timeout_s)
                user_row = page.locator("tr", has_text=new_username).first
                user_row.wait_for(timeout=timeout_ms)
                assert new_email in user_row.inner_text()

                update_result = browser_fetch_json(
                    page,
                    "PATCH",
                    f"/api/proxy/users/{created_user_id}",
                    {
                        "display_name": edited_display_name,
                        "preferred_channel": "smtp",
                        "content_style": "plain",
                    },
                )
                assert update_result["ok"], update_result
                page.reload(wait_until="networkidle")
                wait_for_heading(page, "Users", timeout_ms)
                updated_user = api.get_user(created_user_id)
                assert updated_user.get("display_name") == edited_display_name
                assert updated_user.get("preferred_channel") == "smtp"
                assert updated_user.get("content_style") == "plain"

                page.get_by_role("link", name="API Keys").click()
                wait_for_heading(page, "API Keys", timeout_ms)
                page.get_by_role("button", name="Add API key").click()
                page.select_option("#api-key-owner-adopted", str(created_user_id))
                page.fill("#api-key-prefix-adopted", key_prefix)
                page.fill("#api-key-ttl-adopted", "1")
                page.get_by_role("button", name="Save").click()

                wait_for_text(page, "Created API key", timeout_ms)
                api_key_row = page.locator("tr", has_text=key_prefix).first
                api_key_row.wait_for(timeout=timeout_ms)
                assert str(created_user_id) in api_key_row.inner_text()

                created_key = next(item for item in api.list_api_keys() if item.get("key_prefix") == key_prefix)
                revoke_result = browser_fetch_json(
                    page,
                    "DELETE",
                    f"/api/proxy/admin/api-keys/{created_key['api_key_id']}",
                )
                assert revoke_result["ok"], revoke_result
                wait_for_heading(page, "API Keys", timeout_ms)
                revoked_key = wait_until(
                    lambda: next(
                        (
                            item
                            for item in api.list_api_keys()
                            if item.get("api_key_id") == created_key["api_key_id"]
                            and str(item.get("status", "")).lower() == "revoked"
                        ),
                        None,
                    ),
                    timeout_s,
                    f"revoked API key {created_key['api_key_id']}",
                )
                assert revoked_key["key_prefix"] == key_prefix

                page.get_by_role("link", name="Users").click()
                wait_for_heading(page, "Users", timeout_ms)
                delete_result = browser_fetch_json(
                    page,
                    "DELETE",
                    f"/api/proxy/users/{created_user_id}",
                )
                assert delete_result["ok"], delete_result
                page.get_by_role("link", name="Groups").click()
                wait_for_heading(page, "Groups", timeout_ms)
                page.get_by_role("link", name="Users").click()
                wait_for_heading(page, "Users", timeout_ms)
                wait_until(
                    lambda: not any(item.get("id") == created_user_id for item in api.list_users(new_username)),
                    timeout_s,
                    f"deleted user {created_user_id}",
                )
                wait_until(
                    lambda: page.locator("tr", has_text=new_username).count() == 0,
                    timeout_s,
                    f"user row {new_username} to disappear",
                )
                created_user_id = None
        finally:
            if created_user_id is not None:
                api.delete_user(created_user_id)
