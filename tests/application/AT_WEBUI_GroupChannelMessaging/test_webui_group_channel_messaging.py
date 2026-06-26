#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import time

import pytest

from tests.application.webui_e2e_support import (
    AdminApi,
    api_timeout_s,
    browser_fetch_json,
    extract_message_id_from_status,
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


def test_webui_t3_t5_group_crud_and_role_binding(test_config, test_email_domain):
    base_url = normalize_localhost(require_value(test_config, "web_server.base_url").rstrip("/"))
    api_base_url = normalize_localhost(require_value(test_config, "api_server.base_url").rstrip("/"))
    api_key = require_value(test_config, "api_server.api_key")
    username = require_value(test_config, "web_server.username")
    password = require_value(test_config, "web_server.password")
    timeout_ms = page_timeout_ms(test_config)
    timeout_s = api_timeout_s(test_config)
    suffix = str(int(time.time()))
    created_group_id: int | None = None
    created_user_id: int | None = None

    group_name = f"e2e_notify_group_{suffix}"
    updated_description = f"Updated group {suffix}"
    member_username = f"e2e_notify_member_{suffix}"
    member_email = f"{member_username}{test_email_domain}"

    with AdminApi(api_base_url, api_key, timeout_s) as api:
        try:
            user_response = api.client.post(
                f"{api_base_url}/api/v1/users",
                json={
                    "username": member_username,
                    "email": member_email,
                    "display_name": "E2E Member",
                    "password": "Pw12345!",
                    "role": "viewer",
                },
            )
            user_response.raise_for_status()
            created_user_payload = user_response.json()
            created_user_id = int(created_user_payload.get("id") or created_user_payload.get("user_id"))

            with managed_page("w28a-442-group-rbac", timeout_ms) as page:
                login_via_browser(page, base_url, username, password, timeout_ms)
                page.get_by_role("link", name="Groups").click()
                wait_for_heading(page, "Groups", timeout_ms)

                page.get_by_role("button", name="Add group").click()
                page.fill("#groups-dialog-name", group_name)
                page.fill("#groups-dialog-description", "Initial description")
                page.get_by_placeholder("Select users").fill(member_username)
                page.locator("li[role='option']", has_text=re.compile(member_username)).click()
                page.get_by_role("button", name="Save changes").click()
                wait_for_text(page, f"Created group {group_name}.", timeout_ms)

                created_group_id = api.wait_for_group_id(group_name, timeout_s)
                group_row = page.locator("tr", has_text=group_name).first
                group_row.wait_for(timeout=timeout_ms)
                assert "Initial description" in group_row.inner_text()
                assert member_username in group_row.inner_text()

                members_response = api.client.get(f"{api_base_url}/api/v1/groups/{created_group_id}")
                members_response.raise_for_status()
                members = members_response.json().get("members", [])
                assert len(members) == 1, members
                assert int(members[0]["user_id"]) == created_user_id

                update_result = browser_fetch_json(
                    page,
                    "PATCH",
                    f"/api/proxy/groups/{created_group_id}",
                    {"description": updated_description, "enabled": True},
                )
                assert update_result["ok"], update_result
                page.get_by_role("link", name="Groups").click()
                wait_for_heading(page, "Groups", timeout_ms)
                updated_group_row = page.locator("tr", has_text=group_name).first
                updated_group_row.wait_for(timeout=timeout_ms)
                updated_group = next(
                    item for item in api.list_groups() if item.get("id") == created_group_id
                )
                assert updated_group.get("description") == updated_description

                page.get_by_role("link", name="Groups").click()
                wait_for_heading(page, "Groups", timeout_ms)
                owner_row = page.locator("tr", has_text=group_name).first
                owner_row.wait_for(timeout=timeout_ms)
                owner_row.get_by_role("button", name="Edit").click()
                page.get_by_role("button", name=re.compile(rf"Remove .*{re.escape(member_username)}")).click()
                page.get_by_role("button", name="Save changes").click()
                wait_for_text(page, "Updated group", timeout_ms)
                removed_members_response = api.client.get(f"{api_base_url}/api/v1/groups/{created_group_id}")
                removed_members_response.raise_for_status()
                removed_members = removed_members_response.json().get("members", [])
                assert removed_members == []
                page.get_by_role("link", name="Groups").click()
                wait_for_heading(page, "Groups", timeout_ms)
                removed_row = page.locator("tr", has_text=group_name).first
                removed_row.wait_for(timeout=timeout_ms)

                delete_result = browser_fetch_json(
                    page,
                    "DELETE",
                    f"/api/proxy/groups/{created_group_id}",
                )
                assert delete_result["ok"], delete_result
                page.get_by_role("link", name="Users").click()
                wait_for_heading(page, "Users", timeout_ms)
                page.get_by_role("link", name="Groups").click()
                wait_for_heading(page, "Groups", timeout_ms)
                wait_until(
                    lambda: not any(item.get("id") == created_group_id for item in api.list_groups()),
                    timeout_s,
                    f"deleted group {created_group_id}",
                )
                wait_until(
                    lambda: page.locator("tr", has_text=group_name).count() == 0,
                    timeout_s,
                    f"group row {group_name} to disappear",
                )
                created_group_id = None
        finally:
            if created_group_id is not None:
                api.delete_group(created_group_id)
            if created_user_id is not None:
                api.delete_user(created_user_id)
@pytest.mark.AT
@pytest.mark.webui
@pytest.mark.req("FR-023")


def test_webui_t6_t7_t10_t11_channel_send_group_delivery_tracking(test_config, test_email, test_email_domain):
    base_url = normalize_localhost(require_value(test_config, "web_server.base_url").rstrip("/"))
    api_base_url = normalize_localhost(require_value(test_config, "api_server.base_url").rstrip("/"))
    api_key = require_value(test_config, "api_server.api_key")
    username = require_value(test_config, "web_server.username")
    password = require_value(test_config, "web_server.password")
    timeout_ms = page_timeout_ms(test_config)
    timeout_s = api_timeout_s(test_config) + 30.0
    suffix = str(int(time.time()))

    created_channel_id: int | None = None
    created_group_id: int | None = None
    created_user_id: int | None = None
    created_message_ids: list[int] = []

    channel_name = f"e2e_notify_channel_{suffix}"
    updated_channel_name = f"{channel_name}_updated"
    group_name = f"e2e_notify_group_delivery_{suffix}"
    member_username = f"e2e_notify_target_{suffix}"
    member_email = f"{member_username}{test_email_domain}"
    smtp_config = {
        "host": "mail.example.com",
        "port": 25,
        "username": "operations@cloud-dog.net",
        "password": "StGeorge20@8",
        "from_address": "operations@cloud-dog.net",
        "use_tls": False,
        "use_starttls": False,
        "timeout": 15,
    }

    with AdminApi(api_base_url, api_key, timeout_s) as api:
        try:
            with managed_page("w28a-442-channel-message-delivery", timeout_ms) as page:
                login_via_browser(page, base_url, username, password, timeout_ms)

                page.get_by_role("link", name="Channels").click()
                wait_for_heading(page, "Channels", timeout_ms)
                create_result = browser_fetch_json(
                    page,
                    "POST",
                    "/webapi/proxy/channels",
                    {
                        "name": channel_name,
                        "type": "smtp",
                        "enabled": True,
                        "config": {
                            "host": smtp_config["host"],
                            "port": smtp_config["port"],
                            "username": smtp_config["username"],
                            "password": smtp_config["password"],
                            "from_address": smtp_config["from_address"],
                            "use_tls": smtp_config["use_tls"],
                            "use_starttls": smtp_config["use_starttls"],
                            "timeout": smtp_config["timeout"],
                        },
                    },
                )
                assert create_result["ok"], create_result
                page.reload(wait_until="networkidle")
                wait_for_heading(page, "Channels", timeout_ms)

                created_channel_id = api.wait_for_channel_id(channel_name, timeout_s)
                channel_row = page.locator("tr", has_text=channel_name).first
                channel_row.wait_for(timeout=timeout_ms)
                assert "smtp" in channel_row.inner_text().lower()

                channel_row.get_by_role("button", name="Edit").click()
                page.fill("#channels-edit-name", updated_channel_name)
                page.fill("#channels-smtp-host-adopted", smtp_config["host"])
                page.fill("#channels-smtp-port-adopted", str(smtp_config["port"]))
                page.fill("#channels-smtp-username-adopted", smtp_config["username"])
                page.fill("#channels-smtp-password-adopted", smtp_config["password"])
                page.fill("#channels-smtp-from-address-adopted", test_email)
                page.select_option("#channels-smtp-tls-adopted", "true" if smtp_config["use_tls"] else "false")
                page.get_by_role("button", name="Save").click()
                wait_for_text(page, "Updated channel", timeout_ms)
                renamed_row = page.locator("tr", has_text=updated_channel_name).first
                renamed_row.wait_for(timeout=timeout_ms)
                assert "smtp" in renamed_row.inner_text().lower()

                test_result = browser_fetch_json(
                    page,
                    "POST",
                    f"/api/proxy/channels/{created_channel_id}/test",
                    {"destination": test_email, "test_message": f"E2E test {suffix}"},
                )
                assert test_result["ok"], test_result

                page.get_by_role("link", name="Messages").click()
                wait_for_heading(page, "Messages", timeout_ms)
                page.get_by_role("button", name="Compose message").click()
                page.select_option("#ef-channel", updated_channel_name)
                page.fill("#ef-destination", test_email)
                page.fill("#ef-created_by", "webui-e2e")
                page.fill("#messages-compose-body-adopted", f"E2E personalised message {suffix}")
                page.get_by_role("button", name="Save").click()
                wait_for_text(page, "Created message", timeout_ms)
                personalised_message_id = extract_message_id_from_status(page.locator("main").inner_text())
                created_message_ids.append(personalised_message_id)
                api.wait_for_deliveries(personalised_message_id, timeout_s)

                user_response = api.client.post(
                    f"{api_base_url}/api/v1/users",
                    json={
                        "username": member_username,
                        "email": member_email,
                        "display_name": "E2E Delivery Member",
                        "password": "Pw12345!",
                        "role": "viewer",
                    },
                )
                user_response.raise_for_status()
                created_user_payload = user_response.json()
                created_user_id = int(created_user_payload.get("id") or created_user_payload.get("user_id"))

                group_response = api.client.post(
                    f"{api_base_url}/api/v1/groups",
                    json={"name": group_name, "description": "Delivery group"},
                )
                group_response.raise_for_status()
                created_group_id = int(group_response.json().get("group_id") or group_response.json().get("id"))

                member_response = api.client.post(
                    f"{api_base_url}/api/v1/groups/{created_group_id}/members",
                    json={"user_id": created_user_id, "role": "member"},
                )
                member_response.raise_for_status()

                page.get_by_role("button", name="Compose message").click()
                page.select_option("#ef-channel", updated_channel_name)
                page.fill("#ef-destination", f"group:{group_name}")
                page.fill("#ef-created_by", "webui-e2e")
                page.fill("#messages-compose-body-adopted", f"E2E group message {suffix}")
                page.get_by_role("button", name="Save").click()
                wait_for_text(page, "Created message", timeout_ms)
                group_message_id = extract_message_id_from_status(page.locator("main").inner_text())
                created_message_ids.append(group_message_id)
                deliveries = api.wait_for_deliveries(group_message_id, timeout_s)
                delivery_id = int(deliveries[0]["id"])

                page.get_by_role("link", name="Deliveries").click()
                wait_for_heading(page, "Deliveries", timeout_ms)
                page.fill("#deliveries-message-filter-adopted", str(group_message_id))
                page.select_option("#deliveries-state-filter-adopted", "")
                page.get_by_role("button", name="Refresh deliveries").click()
                assert page.locator("#deliveries-message-filter-adopted").input_value() == str(group_message_id)
                where = f"/api/proxy/deliveries?limit=500&message_id={group_message_id}"
                session_delivery_result = wait_until(
                    lambda: (
                        candidate
                        if candidate["ok"] and candidate["data"].get("items")
                        else None
                    )
                    if (candidate := browser_fetch_json(page, "GET", where))
                    else None,
                    timeout_s,
                    f"delivery proxy result for message {group_message_id}",
                    interval_s=1.0,
                )
                assert session_delivery_result["ok"], session_delivery_result
                session_items = session_delivery_result["data"].get("items", [])
                matched_delivery = next(
                    item for item in session_items if int(item["id"]) == delivery_id and int(item["message_id"]) == group_message_id
                )
                assert matched_delivery["destination"] == member_email

                for message_id in created_message_ids:
                    api.delete_message(message_id)
                created_message_ids.clear()

                page.get_by_role("link", name="Channels").click()
                wait_for_heading(page, "Channels", timeout_ms)
                renamed_row = page.locator("tr", has_text=updated_channel_name).first
                renamed_row.wait_for(timeout=timeout_ms)
                delete_result = browser_fetch_json(
                    page,
                    "DELETE",
                    f"/api/proxy/channels/{created_channel_id}",
                )
                assert delete_result["ok"], delete_result
                assert not any(
                    item.get("id") == created_channel_id for item in api.list_channels()
                )
                created_channel_id = None
        finally:
            for message_id in created_message_ids:
                api.delete_message(message_id)
            if created_group_id is not None:
                api.delete_group(created_group_id)
            if created_user_id is not None:
                api.delete_user(created_user_id)
            if created_channel_id is not None:
                api.delete_channel(created_channel_id)
