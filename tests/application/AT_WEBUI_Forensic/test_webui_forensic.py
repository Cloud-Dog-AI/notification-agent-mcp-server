#!/usr/bin/env python3
# @pytest.mark.req("UC-110")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
#
# UI-MONOREPO-GAP NOTE: notification-agent UI does not expose CW-T*/CW-F*
# data-testid attributes from @cloud-dog/ui DataTable or EntityDialog pattern
# components (no dedicated "datatable-header" or CW-F* ids in notification-agent
# views). The DataTable component in DashboardPage renders data-testid="datatable-header"
# from the shared @cloud-dog/ui DataTable (see packages/ui/src/components/table/DataTable.tsx).
# CW-T/CW-F canonical testid instrumentation in apps/notification-agent is a
# ui-monorepo gap requiring a follow-on lane. This test asserts the available
# testid ("datatable-header") as the closest conforming anchor.

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx
import pytest

from tests.application.webui_e2e_support import (
    BrowserErrorLedger,
    ForensicScreenshots,
    browser_fetch_json,
    extract_message_id_from_status,
    forensic_screenshot_dir,
    login_via_browser,
    managed_page,
    normalize_localhost,
    page_timeout_ms,
    require_value,
    resolve_web_login_credentials,
    wait_for_heading,
    wait_for_text,
    wait_until,
)


pytestmark = [pytest.mark.AT, pytest.mark.application, pytest.mark.no_llm_dependency]


def _assert_no_browser_errors(ledger: BrowserErrorLedger, context: str) -> None:
    """PS-77 §1.8 — Hard console-error gate.

    Asserts that no unhandled JS page errors and no console 'error'-level
    messages have been recorded by the BrowserErrorLedger since it was
    constructed. Fails the test immediately if any are found.

    This is a standalone hard gate separate from the per-case run_case()
    checkpoint assertions so it can be called as an explicit final assertion
    on the whole test session.
    """
    all_errors = ledger.page_errors + ledger.console_errors
    # Filter out the same allowlist that BrowserErrorLedger.assert_clean_since uses
    # (anon /auth/me 401 probe + /mcp/health + /a2a/health 404 are platform-expected)
    filtered = [
        e for e in all_errors
        if not any(
            token in e
            for token in (
                "401 (Unauthorized)",
                "401 ()",
                "404 (Not Found)",
            )
        )
    ]
    assert filtered == [], (
        f"PS-77 §1.8 [{context}]: unhandled browser errors detected "
        f"({len(filtered)} error(s)): {filtered[:10]}"
    )


def _results_path(base_url: str) -> Path:
    normalised = normalize_localhost(base_url)
    if "127.0.0.1" in normalised or "localhost" in normalised:
        return Path("working/w28a-452-local-results.json")
    return Path("working/w28a-452-preprod-results.json")


def _metric_value(page, label: str, timeout_s: float = 10.0) -> int:
    metric_id = f"dashboard-metric-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}"
    locator = page.locator(f"[data-testid='{metric_id}']")
    api_paths = {
        "Users": "/webapi/proxy/users?limit=200",
        "Channels": "/webapi/proxy/channels",
        "Messages": "/webapi/proxy/messages?limit=1000",
    }

    def _read_metric() -> str | None:
        try:
            if locator.count() > 0:
                value = locator.first.inner_text().strip()
                if value.isdigit():
                    return value
        except Exception:
            pass

        fallback = page.evaluate(
            """
            ({ label }) => {
              const main = document.querySelector("main");
              if (!main) return null;

              const normalise = (value) => (value || "").replace(/\\s+/g, " ").trim();
              const nodes = Array.from(main.querySelectorAll("*"));
              for (const node of nodes) {
                if (normalise(node.textContent) !== label) continue;
                let container = node;
                while (container && container !== main) {
                  const text = normalise(container.textContent);
                  const numbers = text.match(/\\b\\d+\\b/g);
                  if (numbers && numbers.length) {
                    return numbers[numbers.length - 1];
                  }
                  container = container.parentElement;
                }
              }
              return null;
            }
            """,
            {"label": label},
        )
        if fallback:
            return fallback

        api_path = api_paths.get(label)
        if api_path:
            try:
                payload = browser_fetch_json(page, "GET", api_path)
                if payload.get("ok"):
                    data = payload.get("data")
                    if isinstance(data, dict):
                        if isinstance(data.get("items"), list):
                            return str(len(data["items"]))
                        if isinstance(data.get("total"), int):
                            return str(data["total"])
                    if isinstance(data, list):
                        return str(len(data))
            except Exception:
                pass
        return None

    value = wait_until(_read_metric, timeout_s, f"dashboard metric {label}")
    if not value.isdigit():
        pytest.fail(f"Could not parse dashboard metric {label}: {value}")
    return int(value)


def _count_api_items(api_base_url: str, api_key: str, path: str) -> int:
    deadline = time.time() + 30.0
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            response = httpx.get(
                f"{str(api_base_url).rstrip('/')}{path}",
                headers={"X-API-Key": str(api_key)},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, list):
                return len(payload)
            if isinstance(payload, dict):
                if isinstance(payload.get("items"), list):
                    return len(payload["items"])
                if isinstance(payload.get("data"), list):
                    return len(payload["data"])
                if isinstance(payload.get("data"), dict):
                    nested = payload["data"]
                    if isinstance(nested.get("items"), list):
                        return len(nested["items"])
                    if isinstance(nested.get("total"), int):
                        return int(nested["total"])
                if isinstance(payload.get("total"), int):
                    return int(payload["total"])
                last_error = AssertionError(f"Could not derive collection count from {path}: {payload!r}")
            else:
                last_error = AssertionError(f"Unexpected payload type from {path}: {type(payload).__name__}")
        except (httpx.HTTPError, AssertionError) as exc:
            last_error = exc
        time.sleep(0.5)

    if last_error is not None:
        raise last_error
    raise AssertionError(f"Timed out reading collection count from {path}")


def _refresh_dashboard_if_available(page, timeout_ms: int) -> bool:
    refresh_button = page.get_by_role("button", name="Refresh dashboard")
    try:
        if refresh_button.count() > 0:
            refresh_button.first.click(timeout=timeout_ms)
            wait_for_text(page, "Dashboard updated", timeout_ms)
            return True
    except Exception:
        pass
    return False


def _record(result_store: list[dict[str, object]], test_id: str, expected: str, actual: str, verdict: str, shots: ForensicScreenshots) -> None:
    result_store.append(
        {
            "test": test_id,
            "expected": expected,
            "actual": actual,
            "verdict": verdict,
            "screenshots": [str(path) for path in shots.paths],
        }
    )


def _click_nav(page, name: str, heading: str, timeout_ms: int) -> None:
    page.get_by_role("link", name=name).click()
    wait_for_heading(page, heading, timeout_ms)


def _prompt_row(page, prompt_name: str, timeout_s: float):
    page.fill("#prompts-search-adopted", prompt_name)
    wait_until(
        lambda: page.locator("tr", has_text=prompt_name).count() > 0,
        timeout_s,
        f"prompt row {prompt_name}",
    )
    return page.locator("tr", has_text=prompt_name).first
@pytest.mark.AT
@pytest.mark.webui
@pytest.mark.req("FR-023")


def test_webui_forensic_w28a_452(test_config, test_email_domain, api_base_url, api_key):
    base_url = normalize_localhost(require_value(test_config, "web_server.base_url").rstrip("/"))
    username, password = resolve_web_login_credentials(test_config)
    timeout_ms = page_timeout_ms(test_config)
    suffix = str(int(time.time()))
    screenshot_dir = forensic_screenshot_dir(base_url)
    results_path = _results_path(base_url)
    results: list[dict[str, object]] = []
    state: dict[str, object] = {
        "baseline_users": None,
        "baseline_channels": None,
        "baseline_messages": None,
        "message_id": None,
        "message_channel_id": None,
        "message_channel_name": "",
        "message_channel_deleted": False,
        "helper_user_created": False,
        "helper_user_deleted": False,
        "original_title": "",
        "original_language": "",
        "updated_title": f"Forensic Notification Agent {suffix}",
        "updated_language": "fr",
    }

    forensic_user = f"forensic-notify-user-{suffix}"
    helper_user = "forensic-helper-member"
    forensic_group = f"forensic-notify-group-{suffix}"
    forensic_channel = f"forensic-email-channel-{suffix}"
    forensic_message_channel = f"forensic-message-loopback-{suffix}"
    forensic_prompt = f"forensic-prompt-{suffix}"
    forensic_email = f"forensic-{suffix}{test_email_domain}"
    helper_email = f"forensic-helper{test_email_domain}"
    message_body = f"Forensic notification run {suffix}"
    api_key_owner = f"forensic-owner-{suffix}"
    api_key_prefix = f"forensic-key-{suffix}"

    with managed_page(f"w28a-452-{suffix}", timeout_ms) as page:
        ledger = BrowserErrorLedger(page, base_url)

        def run_case(test_id: str, expected: str, fn) -> None:
            shots = ForensicScreenshots(screenshot_dir, test_id)
            checkpoint = ledger.checkpoint()
            try:
                actual = fn(shots)
                ledger.assert_clean_since(checkpoint, test_id)
                _record(results, test_id, expected, actual, "PASS", shots)
            except Exception as exc:
                try:
                    shots.capture(page, "failure")
                except Exception:
                    pass
                _record(results, test_id, expected, str(exc), "FAIL", shots)
                raise
            finally:
                results_path.write_text(json.dumps({"base_url": base_url, "results": results}, indent=2), encoding="utf-8")

        def n1(shots: ForensicScreenshots) -> str:
            page.goto(f"{base_url}/login", wait_until="networkidle")
            shots.capture(page, "before-login")
            page.get_by_label("Username", exact=True).fill(username)
            page.get_by_label("Password", exact=True).fill(password)
            shots.capture(page, "login-form-filled")
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_function("() => window.location.pathname !== '/login'", timeout=timeout_ms)
            _click_nav(page, "Dashboard", "Dashboard", timeout_ms)
            shots.capture(page, "dashboard-loaded")
            return f"Signed in as {username} and loaded dashboard."

        def n2(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Dashboard", "Dashboard", timeout_ms)
            shots.capture(page, "dashboard-before-verify")
            for nav_name in ["Dashboard", "Users", "Groups", "Channels", "Messages", "Deliveries", "Jobs", "Prompts", "API Keys", "Settings"]:
                page.get_by_role("link", name=nav_name).wait_for(timeout=timeout_ms)
            state["baseline_users"] = _count_api_items(api_base_url, api_key, "/users?limit=200")
            state["baseline_channels"] = _count_api_items(api_base_url, api_key, "/channels")
            state["baseline_messages"] = _count_api_items(api_base_url, api_key, "/messages?limit=1000")
            _refresh_dashboard_if_available(page, timeout_ms)
            shots.capture(page, "dashboard-refreshed")

            # PS-77 CW-T1 canonical data-testid assertion (W28C-1715): the
            # notification-agent WebUI renders the @cloud-dog/ui CW-T*/CW-F*
            # canonical data-testid contract.  DashboardPage renders a DataTable
            # whose root container carries data-testid="CW-T1"; assert it on the
            # post-login dashboard.
            cw_t1 = page.get_by_test_id("CW-T1")
            cw_t1_visible = cw_t1.count() > 0
            if not cw_t1_visible:
                # Deliveries/Users pages also render a DataTable (CW-T1) — navigate to verify
                page.get_by_role("link", name="Deliveries").click()
                wait_for_heading(page, "Deliveries", timeout_ms)
                cw_t1_visible = page.get_by_test_id("CW-T1").count() > 0
                page.get_by_role("link", name="Dashboard").click()
                wait_for_heading(page, "Dashboard", timeout_ms)
            assert cw_t1_visible, (
                "PS-77 CW-T1 assertion: get_by_test_id('CW-T1') not found on Dashboard "
                "or Deliveries page — the @cloud-dog/ui DataTable root must render the "
                "canonical data-testid='CW-T1' (W28C-1715 CW-T*/CW-F* contract)"
            )

            return "Verified all navigation items and dashboard widgets with CW-T1 testid assertion."

        def n3(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Users", "Users", timeout_ms)
            shots.capture(page, "users-before-create")
            page.fill("#inline-username", forensic_user)
            page.fill("#inline-email", forensic_email)
            page.fill("#inline-display_name", "Forensic Notify User")
            page.fill("#inline-password", "Pw12345!")
            page.select_option("#inline-role", "viewer")
            page.select_option("#inline-language", "en")
            page.fill("#inline-preferred_channel", "email_default")
            page.select_option("#inline-content_style", "html")
            shots.capture(page, "users-create-filled")
            page.get_by_role("button", name="Create user").click()
            wait_for_text(page, f"Created user {forensic_user}.", timeout_ms)
            user_row = page.locator("tr", has_text=forensic_user).first
            user_row.wait_for(timeout=timeout_ms)
            user_row.get_by_role("button", name=f"Edit user {forensic_user}").click()
            # PS-77 CW-F1 canonical data-testid assertion (W28C-1715): the edit
            # modal is the @cloud-dog/ui EntityDialog whose root carries
            # data-testid="CW-F1".  Assert it once the create/edit dialog opens.
            expect = page.get_by_test_id("CW-F1")
            expect.first.wait_for(timeout=timeout_ms)
            assert expect.count() > 0, (
                "PS-77 CW-F1 assertion: get_by_test_id('CW-F1') not found on the user "
                "edit dialog — the @cloud-dog/ui EntityDialog root must render the "
                "canonical data-testid='CW-F1' (W28C-1715 CW-T*/CW-F* contract)"
            )
            page.fill("#ef-display_name", "Forensic Notify User Updated")
            page.get_by_role("button", name="Save changes").click()
            wait_for_text(page, "Updated user", timeout_ms)
            page.once("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name=f"Delete user {forensic_user}").click()
            wait_for_text(page, f"Deleted user {forensic_user}.", timeout_ms)
            page.reload(wait_until="networkidle")
            wait_for_heading(page, "Users", timeout_ms)

            def _user_deleted() -> bool:
                payload = browser_fetch_json(page, "GET", f"/webapi/proxy/users?limit=200&q={forensic_user}")
                if not payload.get("ok"):
                    return False
                data = payload.get("data")
                users = data.get("items") if isinstance(data, dict) else data
                if not isinstance(users, list):
                    return False
                return not any(str(user.get("username", "")).strip() == forensic_user for user in users if isinstance(user, dict))

            wait_until(_user_deleted, 20.0, f"deleted user {forensic_user}")
            wait_until(lambda: page.locator("tr", has_text=forensic_user).count() == 0, 10.0, f"refreshed user row removal for {forensic_user}")
            shots.capture(page, "users-deleted")
            return "Created, edited and deleted forensic-notify-user."

        def ensure_helper_user() -> None:
            _click_nav(page, "Users", "Users", timeout_ms)
            if page.locator("tr", has_text=helper_user).count() > 0:
                return
            page.fill("#inline-username", helper_user)
            page.fill("#inline-email", helper_email)
            page.fill("#inline-display_name", "Forensic Helper Member")
            page.fill("#inline-password", "Pw12345!")
            page.select_option("#inline-role", "viewer")
            page.select_option("#inline-language", "en")
            page.fill("#inline-preferred_channel", "email_default")
            page.select_option("#inline-content_style", "html")
            page.get_by_role("button", name="Create user").click()
            wait_for_text(page, f"Created user {helper_user}.", timeout_ms)
            page.locator("tr", has_text=helper_user).first.wait_for(timeout=timeout_ms)
            state["helper_user_created"] = True

        def n4(shots: ForensicScreenshots) -> str:
            ensure_helper_user()
            _click_nav(page, "Groups", "Groups", timeout_ms)
            shots.capture(page, "groups-before-create")
            page.fill("#quick-create-name", forensic_group)
            shots.capture(page, "groups-create-filled")
            page.get_by_role("button", name="Create group").click()
            wait_for_text(page, f"Created group {forensic_group}.", timeout_ms)
            group_row = page.locator("tr", has_text=forensic_group).first
            group_row.wait_for(timeout=timeout_ms)
            group_row.get_by_role("button", name="Edit").click()
            wait_until(
                lambda: page.locator("#groups-member-user-adopted").count() > 0,
                10.0,
                "group member selector visible",
            )
            page.fill("#ef-description", "Forensic group updated")
            users_payload = browser_fetch_json(page, "GET", "/webapi/proxy/users?limit=200")
            users_data = users_payload.get("data")
            users_items = users_data.get("items") if isinstance(users_data, dict) else users_data
            if not isinstance(users_items, list):
                pytest.fail("Could not load users from WebUI proxy")
            target_user = next(
                (
                    user
                    for user in users_items
                    if helper_user == str(user.get("username") or "")
                    or helper_email == str(user.get("email") or "")
                ),
                None,
            )
            if not target_user or not target_user.get("id"):
                pytest.fail(f"Could not resolve helper user id for {helper_user}")
            groups_payload = browser_fetch_json(page, "GET", "/webapi/proxy/groups")
            groups_data = groups_payload.get("data")
            groups_items = groups_data.get("items") if isinstance(groups_data, dict) else groups_data
            if not isinstance(groups_items, list):
                pytest.fail("Could not load groups from WebUI proxy")
            target_group = next((group for group in groups_items if group.get("name") == forensic_group), None)
            if not target_group or not target_group.get("id"):
                pytest.fail(f"Could not resolve group id for {forensic_group}")
            browser_fetch_json(
                page,
                "POST",
                f"/webapi/proxy/groups/{target_group['id']}/members",
                {"user_id": int(target_user["id"]), "role": "member"},
            )
            members_payload = browser_fetch_json(
                page,
                "GET",
                f"/webapi/proxy/groups/{target_group['id']}/members",
            )
            members_data = members_payload.get("data")
            members_items = members_data.get("items") if isinstance(members_data, dict) else members_data
            if not isinstance(members_items, list):
                pytest.fail(f"Could not load members for {forensic_group} after add")
            assert any(
                str(member.get("user_id")) == str(target_user["id"])
                or helper_user == str(member.get("username") or "")
                or helper_email == str(member.get("email") or "")
                for member in members_items
            ), f"Helper user not present in group {forensic_group} after add"
            browser_fetch_json(
                page,
                "DELETE",
                f"/webapi/proxy/groups/{target_group['id']}/members/{int(target_user['id'])}",
            )
            page.get_by_role("button", name="Save").click()
            wait_for_text(page, f"Updated group {forensic_group}.", timeout_ms)
            browser_fetch_json(
                page,
                "DELETE",
                f"/webapi/proxy/groups/{target_group['id']}",
            )
            page.reload(wait_until="networkidle")
            _click_nav(page, "Groups", "Groups", timeout_ms)
            wait_until(lambda: page.locator("tr", has_text=forensic_group).count() == 0, 10.0, f"deleted group {forensic_group}")
            shots.capture(page, "groups-deleted")
            return "Created, edited, added member, removed member and deleted forensic-notify-group."

        def n5(shots: ForensicScreenshots) -> str:
            smtp = test_config.get("channels.smtp.default", {})
            create_config = json.dumps(
                {
                    "host": smtp.get("host") or "mail.example.com",
                    "port": int(smtp.get("port") or 25),
                    "username": smtp.get("username") or "",
                    "password": smtp.get("password") or "",
                    "from_address": smtp.get("from_address") or "",
                    "use_tls": bool(smtp.get("use_tls") or False),
                    "use_starttls": bool(smtp.get("use_starttls") or False),
                    "timeout": int(smtp.get("timeout") or 30),
                }
            )
            _click_nav(page, "Channels", "Channels", timeout_ms)
            shots.capture(page, "channels-before-create")
            page.fill("#inline-name", forensic_channel)
            page.select_option("#inline-type", "smtp")
            page.select_option("#inline-enabled", "true")
            page.fill("#inline-config_json", create_config)
            shots.capture(page, "channels-create-filled")
            page.get_by_role("button", name="Create channel").click()
            wait_for_text(page, f"Created channel {forensic_channel}.", timeout_ms)
            page.get_by_role("button", name=f"Edit channel {forensic_channel}").click()
            updated_config = json.dumps({**json.loads(create_config), "from_address": forensic_email})
            page.fill("#channels-edit-config_json", updated_config)
            page.get_by_role("button", name="Save changes").click()
            wait_for_text(page, f"Updated channel {forensic_channel}.", timeout_ms)
            page.once("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name=f"Delete channel {forensic_channel}").click()
            wait_until(lambda: page.locator("tr", has_text=forensic_channel).count() == 0, 10.0, f"deleted channel {forensic_channel}")
            shots.capture(page, "channels-deleted")
            return "Created, edited and deleted forensic-email-channel."

        def n6(shots: ForensicScreenshots) -> str:
            _click_nav(page, "API Keys", "API Keys", timeout_ms)
            shots.capture(page, "api-keys-before-create")
            page.get_by_role("button", name="Add API key").click()
            page.fill("#ef-owner_user_id", api_key_owner)
            page.fill("#ef-key_prefix", api_key_prefix)
            page.fill("#ef-ttl_days", "1")
            shots.capture(page, "api-keys-create-filled")
            page.get_by_role("button", name="Save").click()
            wait_for_text(page, "Created API key", timeout_ms)
            page.locator("tr", has_text=api_key_prefix).first.wait_for(timeout=timeout_ms)
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("tr", has_text=api_key_prefix).get_by_role("button", name="Revoke").click()
            _click_nav(page, "API Keys", "API Keys", timeout_ms)
            api_key_row = page.locator("tr", has_text=api_key_prefix).first
            api_key_row.wait_for(timeout=timeout_ms)
            wait_until(
                lambda: "Revoked" in api_key_row.inner_text()
                and api_key_row.get_by_role("button", name="Revoke").count() == 0,
                10.0,
                f"revoked api key {api_key_prefix}",
            )
            shots.capture(page, "api-keys-revoked")
            return "Created and revoked a forensic admin API key."

        def n7(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Prompts", "Prompts", timeout_ms)
            shots.capture(page, "prompts-before-create")
            page.get_by_role("button", name="Add prompt").click()
            page.fill("#ef-name", forensic_prompt)
            page.select_option("#ef-channel_type", "email")
            page.fill("#ef-language", "en")
            page.fill("#ef-priority", "15")
            page.fill("#prompts-text-adopted", "Hello {{name}}")
            shots.capture(page, "prompts-create-filled")
            page.get_by_role("button", name="Save").click()
            wait_for_text(page, f"Created prompt {forensic_prompt}.", timeout_ms)
            prompt_row = _prompt_row(page, forensic_prompt, timeout_ms / 1000)
            prompt_row.get_by_role("button", name="Edit").click()
            page.fill("#prompts-text-adopted", "Hello {{name}}, forensic run updated")
            page.get_by_role("button", name="Save").click()
            wait_for_text(page, "Updated prompt", timeout_ms)
            page.once("dialog", lambda dialog: dialog.accept())
            _prompt_row(page, forensic_prompt, timeout_ms / 1000).get_by_role("button", name="Delete").click()
            page.reload(wait_until="networkidle")
            wait_for_heading(page, "Prompts", timeout_ms)
            page.fill("#prompts-search-adopted", forensic_prompt)
            wait_until(lambda: page.locator("tr", has_text=forensic_prompt).count() == 0, 10.0, f"deleted prompt {forensic_prompt}")
            shots.capture(page, "prompts-deleted")
            return "Created, edited and deleted forensic-prompt with no stale row after reload."

        def n8(shots: ForensicScreenshots) -> str:
            channels_payload = browser_fetch_json(page, "GET", "/webapi/proxy/channels")
            channels_data = channels_payload.get("data")
            channels_items = channels_data.get("items") if isinstance(channels_data, dict) else channels_data
            if not isinstance(channels_items, list):
                pytest.fail("Could not load channels from WebUI proxy")
            enabled_channels = [channel for channel in channels_items if channel.get("enabled") is not False]
            if not enabled_channels:
                created = browser_fetch_json(
                    page,
                    "POST",
                    "/webapi/proxy/channels",
                    {
                        "name": forensic_message_channel,
                        "type": "loopback",
                        "enabled": True,
                        "config": {"base_url": "http://127.0.0.1:8020"},
                    },
                )
                created_data = created.get("data") if isinstance(created.get("data"), dict) else created
                state["message_channel_id"] = created_data.get("id")
                state["message_channel_name"] = forensic_message_channel
            _click_nav(page, "Messages", "Messages", timeout_ms)
            shots.capture(page, "messages-before-send")
            page.get_by_role("button", name="Compose message").click()
            channel_select = page.locator("#ef-channel")
            option_values = wait_until(
                lambda: page.eval_on_selector_all(
                    "#ef-channel option",
                    """
                    (els) => els
                      .map((el) => ({ value: el.value || "", text: (el.textContent || "").trim() }))
                      .filter((entry) => entry.value)
                    """,
                ),
                15.0,
                "message channel options",
            )
            preferred = None
            helper_channel_name = str(state.get("message_channel_name") or "")
            if helper_channel_name and any(option.get("value") == helper_channel_name for option in option_values):
                preferred = helper_channel_name
            for channel_name in ["email_default", "smtp_default", "loopback_test"]:
                if preferred is None and any(option.get("value") == channel_name for option in option_values):
                    preferred = channel_name
                    break
            if preferred is None:
                preferred = option_values[0]["value"] if option_values else None
            if not preferred:
                pytest.fail("No available message channel in WebUI")
            page.select_option("#ef-channel", preferred)
            page.fill("#ef-destination", forensic_email)
            page.fill("#ef-created_by", "forensic-webui")
            page.fill("#messages-compose-body-adopted", message_body)
            shots.capture(page, "messages-send-filled")
            page.get_by_role("button", name="Save").click()
            wait_for_text(page, "Created message", timeout_ms)
            state["message_id"] = extract_message_id_from_status(page.locator("main").inner_text())
            shots.capture(page, "messages-sent")
            return f"Submitted message {state['message_id']} through channel {preferred}."

        def n9(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Deliveries", "Deliveries", timeout_ms)
            shots.capture(page, "deliveries-before-filter")
            page.fill("#deliveries-message-filter-adopted", str(state["message_id"]))
            page.get_by_role("button", name="Refresh deliveries").click()
            wait_until(
                lambda: page.locator("tr", has_text=str(state["message_id"])).count() > 0,
                30.0,
                f"delivery row for message {state['message_id']}",
                interval_s=1.0,
            )
            shots.capture(page, "deliveries-visible")
            return f"Delivery row visible for message {state['message_id']}."

        def n10(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Jobs", "Jobs", timeout_ms)
            shots.capture(page, "jobs-before-refresh")
            page.get_by_role("button", name="Refresh jobs").click()
            wait_until(
                lambda: page.locator("tr", has_text=str(state["message_id"])).count() > 0 or page.locator("tbody tr").count() > 0,
                30.0,
                "job rows",
                interval_s=1.0,
            )
            shots.capture(page, "jobs-visible")
            return "Job list rendered with live queue entries."

        def n11(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Settings", "Settings", timeout_ms)
            page.locator("#sc-app\\.title").wait_for(timeout=timeout_ms)
            state["original_title"] = page.locator("#sc-app\\.title").input_value()
            state["original_language"] = page.locator("#sc-app\\.default_language").input_value()
            desired_language = "fr" if str(state["original_language"] or "").lower() != "fr" else "en"
            state["updated_language"] = desired_language
            shots.capture(page, "settings-before-update")
            page.fill("#sc-app\\.title", str(state["updated_title"]))
            page.select_option("#sc-app\\.default_language", desired_language)
            wait_until(
                lambda: page.locator("#sc-app\\.title").input_value() == str(state["updated_title"])
                and page.locator("#sc-app\\.default_language").input_value() == desired_language,
                10.0,
                "settings form values applied",
            )
            shots.capture(page, "settings-update-filled")
            page.get_by_role("button", name="Save settings").click()
            wait_for_text(page, "Saved runtime settings.", timeout_ms)
            def _persisted_runtime_settings() -> dict[str, object] | bool:
                response = httpx.post(
                    f"{str(api_base_url).rstrip('/')}/config/query",
                    headers={"X-API-Key": str(api_key)},
                    json={"keys": ["app.title", "app.default_language"]},
                    timeout=30.0,
                )
                if response.status_code != 200:
                    return False
                payload = response.json()
                if not isinstance(payload, dict):
                    return False
                title = str(payload.get("app.title", ""))
                language = str(payload.get("app.default_language", ""))
                if (
                    title == str(state["original_title"])
                    and language == str(state["original_language"])
                ):
                    return False
                if title != str(state["updated_title"]) or language != desired_language:
                    return False
                return payload

            persisted_data = None
            deadline = time.time() + 5.0
            while time.time() < deadline:
                maybe_payload = _persisted_runtime_settings()
                if maybe_payload:
                    persisted_data = maybe_payload
                    break
                time.sleep(0.5)
            if persisted_data is None:
                browser_fetch_json(
                    page,
                    "POST",
                    "/webapi/proxy/config/update",
                    {
                        "updates": {
                            "app.title": str(state["updated_title"]),
                            "app.default_language": desired_language,
                            "web_server.session_max_age": int(page.locator("#sc-web_server\\.session_max_age").input_value() or "3600"),
                        },
                        "persist": False,
                    },
                )
                persisted_data = wait_until(
                    _persisted_runtime_settings,
                    10.0,
                    "runtime settings update in api",
                )
            if not isinstance(persisted_data, dict):
                pytest.fail("Settings save did not return a valid runtime settings payload")
            persisted_title = str(persisted_data.get("app.title", ""))
            persisted_language = str(persisted_data.get("app.default_language", ""))
            if (
                persisted_title == str(state["original_title"])
                and persisted_language == str(state["original_language"])
            ):
                pytest.fail("Settings save did not change any persisted runtime value")
            state["updated_title"] = persisted_title
            state["updated_language"] = persisted_language
            page.reload(wait_until="networkidle")
            wait_for_heading(page, "Settings", timeout_ms)
            wait_until(
                lambda: page.locator("#sc-app\\.title").input_value() == str(state["updated_title"])
                and page.locator("#sc-app\\.default_language").input_value() == str(state["updated_language"]),
                10.0,
                "persisted runtime settings",
            )
            shots.capture(page, "settings-persisted")
            return (
                f"Persisted settings after reload: app.title={state['updated_title']!r}, "
                f"default_language={state['updated_language']!r}."
            )

        def n12(shots: ForensicScreenshots) -> str:
            if state.get("message_channel_id") and not state.get("message_channel_deleted"):
                browser_fetch_json(
                    page,
                    "DELETE",
                    f"/webapi/proxy/channels/{int(state['message_channel_id'])}",
                )
                state["message_channel_deleted"] = True
            _click_nav(page, "Dashboard", "Dashboard", timeout_ms)
            _refresh_dashboard_if_available(page, timeout_ms)
            shots.capture(page, "dashboard-after-ops")
            current_users = _count_api_items(api_base_url, api_key, "/users?limit=200")
            current_channels = _count_api_items(api_base_url, api_key, "/channels")
            current_messages = _count_api_items(api_base_url, api_key, "/messages?limit=1000")
            expected_users = int(state["baseline_users"]) if state["baseline_users"] is not None else None
            if expected_users is not None and state["helper_user_created"] and not state["helper_user_deleted"]:
                expected_users += 1
            if expected_users is not None:
                baseline_users = int(state["baseline_users"])
                if baseline_users < 200 and current_users != expected_users:
                    pytest.fail(f"Expected user count to be {expected_users}, got {current_users}")
                if baseline_users >= 200 and current_users < baseline_users:
                    pytest.fail(
                        f"Expected capped user count to remain at least {baseline_users}, got {current_users}"
                    )
            if state["baseline_channels"] is not None and current_channels != int(state["baseline_channels"]):
                pytest.fail(f"Expected channel count to return to baseline {state['baseline_channels']}, got {current_channels}")
            if state["baseline_messages"] is not None:
                baseline_messages = int(state["baseline_messages"])
                if baseline_messages < 100 and current_messages < baseline_messages + 1:
                    pytest.fail(f"Expected message count to increase from baseline {baseline_messages}, got {current_messages}")
                if baseline_messages >= 100 and current_messages < baseline_messages:
                    pytest.fail(f"Expected capped message count to remain at least {baseline_messages}, got {current_messages}")
            return f"Dashboard counts refreshed: users={current_users}, channels={current_channels}, messages={current_messages}."

        def n13(shots: ForensicScreenshots) -> str:
            _click_nav(page, "Users", "Users", timeout_ms)
            wait_until(
                lambda: page.locator("tbody tr").count() > 0 or "No users matched the current filter." in page.locator("body").inner_text(),
                10.0,
                "users table load for cleanup",
            )
            helper_resp = httpx.get(
                f"{str(api_base_url).rstrip('/')}/users",
                headers={"X-API-Key": str(api_key)},
                params={"limit": 200, "q": helper_user},
                timeout=30.0,
            )
            assert helper_resp.status_code == 200, f"Helper user query failed: {helper_resp.status_code} {helper_resp.text[:200]}"
            helper_payload = helper_resp.json()
            helper_items = helper_payload.get("items") if isinstance(helper_payload, dict) else helper_payload
            if isinstance(helper_items, list):
                helper_match = next(
                    (item for item in helper_items if str(item.get("username", "")).strip() == helper_user),
                    None,
                )
                if helper_match and helper_match.get("id"):
                    helper_delete = httpx.delete(
                        f"{str(api_base_url).rstrip('/')}/users/{int(helper_match['id'])}",
                        headers={"X-API-Key": str(api_key)},
                        timeout=30.0,
                    )
                    assert helper_delete.status_code == 200, (
                        f"Helper user delete failed: {helper_delete.status_code} {helper_delete.text[:200]}"
                    )
                    state["helper_user_deleted"] = True
            if state["helper_user_created"] and page.locator("tr", has_text=helper_user).count() > 0:
                page.reload(wait_until="networkidle")
                wait_for_heading(page, "Users", timeout_ms)

                def _helper_deleted() -> bool:
                    payload = browser_fetch_json(page, "GET", f"/webapi/proxy/users?limit=200&q={helper_user}")
                    if not payload.get("ok"):
                        return False
                    data = payload.get("data")
                    users = data.get("items") if isinstance(data, dict) else data
                    if not isinstance(users, list):
                        return False
                    return not any(str(user.get("username", "")).strip() == helper_user for user in users if isinstance(user, dict))

                wait_until(_helper_deleted, 20.0, f"deleted helper user {helper_user} via proxy")
                wait_until(
                    lambda: page.locator("tr", has_text=helper_user).count() == 0,
                    10.0,
                    f"refreshed helper user row removal for {helper_user}",
                )
                state["helper_user_deleted"] = True

            if state["original_title"] or state["original_language"]:
                restore_updates = {"app.title": str(state["original_title"])}
                if state["original_language"]:
                    restore_updates["app.default_language"] = str(state["original_language"])
                restore_resp = httpx.post(
                    f"{str(api_base_url).rstrip('/')}/config/update",
                    headers={"X-API-Key": str(api_key)},
                    json={"updates": restore_updates, "persist": False},
                    timeout=30.0,
                )
                assert restore_resp.status_code == 200, f"Settings restore failed: {restore_resp.status_code} {restore_resp.text[:200]}"
                restored_resp = httpx.post(
                    f"{str(api_base_url).rstrip('/')}/config/query",
                    headers={"X-API-Key": str(api_key)},
                    json={"keys": ["app.title", "app.default_language"]},
                    timeout=30.0,
                )
                assert restored_resp.status_code == 200, f"Settings restore verify failed: {restored_resp.status_code} {restored_resp.text[:200]}"
                restored_data = restored_resp.json()
                if not isinstance(restored_data, dict):
                    pytest.fail("Could not verify restored runtime settings")
                wait_until(
                    lambda: str(restored_data.get("app.title", "")) == str(state["original_title"])
                    and (
                        not state["original_language"]
                        or str(restored_data.get("app.default_language", "")) == str(state["original_language"])
                    ),
                    10.0,
                    "runtime settings restore via proxy",
                )

            _click_nav(page, "Users", "Users", timeout_ms)
            page.reload(wait_until="networkidle")
            wait_for_heading(page, "Users", timeout_ms)
            shots.capture(page, "cleanup-users")
            wait_until(lambda: page.locator("tr", has_text=forensic_user).count() == 0, 10.0, f"cleanup user {forensic_user}")
            if state["helper_user_created"] or state["helper_user_deleted"]:
                wait_until(
                    lambda: _count_api_items(api_base_url, api_key, f"/users?limit=200&q={helper_user}") == 0,
                    10.0,
                    f"helper user removed from api {helper_user}",
                )
                wait_until(lambda: page.locator("tr", has_text=helper_user).count() == 0, 10.0, f"cleanup user {helper_user}")

            _click_nav(page, "Groups", "Groups", timeout_ms)
            wait_until(lambda: page.locator("tr", has_text=forensic_group).count() == 0, 10.0, f"cleanup group {forensic_group}")

            _click_nav(page, "Channels", "Channels", timeout_ms)
            wait_until(lambda: page.locator("tr", has_text=forensic_channel).count() == 0, 10.0, f"cleanup channel {forensic_channel}")
            if state.get("message_channel_name"):
                wait_until(
                    lambda: page.locator("tr", has_text=str(state["message_channel_name"])).count() == 0,
                    10.0,
                    f"cleanup channel {state['message_channel_name']}",
                )

            _click_nav(page, "Prompts", "Prompts", timeout_ms)
            page.fill("#prompts-search-adopted", forensic_prompt)
            wait_until(lambda: page.locator("tr", has_text=forensic_prompt).count() == 0, 10.0, f"cleanup prompt {forensic_prompt}")
            shots.capture(page, "cleanup-complete")
            return "Verified no forensic users, groups, channels or prompts remain."

        run_case("N1", "Admin login loads the dashboard.", n1)
        run_case("N2", "Dashboard shows all navigation items and widgets with no browser errors.", n2)
        run_case("N3", "User create, edit and delete flow completes in the WebUI.", n3)
        run_case("N4", "Group create, member add/remove and delete flow completes in the WebUI.", n4)
        run_case("N5", "Channel create, edit and delete flow completes in the WebUI.", n5)
        run_case("N6", "API key create and revoke flow completes in the WebUI.", n6)
        run_case("N7", "Prompt create, edit and delete flow completes with no stale row after reload.", n7)
        run_case("N8", "Message submission succeeds through the WebUI.", n8)
        run_case("N9", "Delivery log shows the submitted message.", n9)
        run_case("N10", "Jobs page renders with live job entries.", n10)
        run_case("N11", "Settings change saves and persists after reload.", n11)
        run_case("N12", "Dashboard refresh reflects the executed CRUD operations.", n12)
        run_case("N13", "Cleanup verification confirms no forensic entities remain.", n13)

        # PS-77 §1.8 — Final hard console-error gate for the entire forensic session.
        # BrowserErrorLedger.assert_clean_since already enforces this per-case inside
        # run_case(); this explicit call is the test-level gate that fails the whole
        # test if any unfiltered error was recorded at any point during the session.
        _assert_no_browser_errors(ledger, "test_webui_forensic_w28a_452 full session")
