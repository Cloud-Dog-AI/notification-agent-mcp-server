#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar
from urllib.parse import urlparse

import httpx
import pytest
from playwright.sync_api import Page, sync_playwright


SCREENSHOT_DIR = Path("working/W28A-442-screenshots")
FORENSIC_LOCAL_SCREENSHOT_DIR = Path("working/W28A-452-local-screenshots")
FORENSIC_PREPROD_SCREENSHOT_DIR = Path("working/W28A-452-preprod-screenshots")
T = TypeVar("T")


def require_value(test_config: Any, key: str) -> str:
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"Missing required test config: {key}")
    return str(value)


def normalize_localhost(url: str) -> str:
    return url.replace("://localhost", "://127.0.0.1")


def page_timeout_ms(test_config: Any) -> int:
    timeout = test_config.get("test.at18.web_timeout") or 45
    return int(float(timeout) * 1000)


def api_timeout_s(test_config: Any) -> float:
    timeout = test_config.get("api.timeout") or 45
    return float(timeout)


def test_suffix() -> str:
    return str(int(time.time() * 1000))


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or "step"


def resolve_web_login_credentials(test_config: Any) -> tuple[str, str]:
    username = os.environ.get("CLOUD_DOG_WEB_LOGIN_USERNAME") or test_config.get("web_server.username")
    password = os.environ.get("CLOUD_DOG_WEB_LOGIN_PASSWORD") or test_config.get("web_server.password")
    if not username or not password:
        pytest.fail("Missing WebUI login credentials")
    return str(username), str(password)


def forensic_screenshot_dir(base_url: str) -> Path:
    normalised = normalize_localhost(base_url)
    if "127.0.0.1" in normalised or "localhost" in normalised:
        return FORENSIC_LOCAL_SCREENSHOT_DIR
    return FORENSIC_PREPROD_SCREENSHOT_DIR


def wait_until(predicate: Callable[[], T | None | bool], timeout_s: float, description: str, interval_s: float = 0.5) -> T | bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval_s)
    pytest.fail(f"Timed out waiting for {description}")


def browser_fetch_json(page: Page, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return page.evaluate(
        """
        async ({ method, path, payload }) => {
          const options = { method, credentials: "same-origin", headers: {} };
          if (payload !== null) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(payload);
          }
          const response = await fetch(path, options);
          const text = await response.text();
          let data = text;
          try {
            data = text ? JSON.parse(text) : null;
          } catch (_error) {}
          return { ok: response.ok, status: response.status, data };
        }
        """,
        {"method": method.upper(), "path": path, "payload": payload},
    )


def wait_for_text(page: Page, text: str, timeout_ms: int) -> None:
    page.get_by_text(text, exact=False).wait_for(timeout=timeout_ms)


def wait_for_heading(page: Page, heading: str, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    candidates = [
        lambda: page.locator("h1", has_text=heading).count() > 0,
        lambda: page.locator("h2", has_text=heading).count() > 0,
        lambda: page.get_by_role("heading", name=heading, exact=False).count() > 0,
    ]
    while time.time() < deadline:
        for candidate in candidates:
            try:
                if candidate():
                    return
            except Exception:
                continue
        time.sleep(0.1)
    pytest.fail(f"Timed out waiting for heading {heading!r}")


def submit_entity_form(page: Page) -> None:
    page.locator('form[aria-label="Entity form"]').evaluate("(form) => form.requestSubmit()")


def login_via_browser(page: Page, base_url: str, username: str, password: str, timeout_ms: int) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_function("() => window.location.pathname !== '/login'", timeout=timeout_ms)
    page.wait_for_timeout(1000)
    assert page.context.cookies(), "Expected an authenticated session cookie after login"


@contextmanager
def managed_page(test_name: str, timeout_ms: int) -> Iterator[Page]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(timeout_ms)
        screenshot = SCREENSHOT_DIR / f"{test_name}.png"
        try:
            yield page
        except Exception:
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                pass
            raise
        finally:
            try:
                page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                pass
            browser.close()


class BrowserErrorLedger:
    def __init__(self, page: Page, base_url: str) -> None:
        parsed = urlparse(normalize_localhost(base_url))
        self._origin = f"{parsed.scheme}://{parsed.netloc}"
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self.http_errors: list[str] = []
        page.on("console", self._on_console)
        page.on("pageerror", self._on_pageerror)
        page.on("response", self._on_response)

    def checkpoint(self) -> tuple[int, int, int]:
        return (len(self.console_errors), len(self.page_errors), len(self.http_errors))

    def assert_clean_since(self, checkpoint: tuple[int, int, int], context: str) -> None:
        console_errors = self.console_errors[checkpoint[0]:]
        page_errors = self.page_errors[checkpoint[1]:]
        http_errors = self.http_errors[checkpoint[2]:]
        ignored_auth_probe = 0
        ignored_health_probes = 0
        filtered_http_errors: list[str] = []
        for entry in http_errors:
            if entry == f"http:401:GET:{self._origin}/auth/me":
                ignored_auth_probe += 1
                continue
            if entry in {
                f"http:404:GET:{self._origin}/mcp/health",
                f"http:404:GET:{self._origin}/a2a/health",
            }:
                ignored_health_probes += 1
                continue
            filtered_http_errors.append(entry)

        filtered_console_errors = list(console_errors)
        if ignored_auth_probe:
            generic_401_messages = [
                "console:Failed to load resource: the server responded with a status of 401 (Unauthorized)",
                "console:Failed to load resource: the server responded with a status of 401 ()",
            ]
            while ignored_auth_probe > 0:
                removed = False
                for message in generic_401_messages:
                    if message in filtered_console_errors:
                        filtered_console_errors.remove(message)
                        ignored_auth_probe -= 1
                        removed = True
                        break
                if not removed:
                    break
        if ignored_health_probes:
            generic_404_message = "console:Failed to load resource: the server responded with a status of 404 (Not Found)"
            while ignored_health_probes > 0 and generic_404_message in filtered_console_errors:
                filtered_console_errors.remove(generic_404_message)
                ignored_health_probes -= 1
        if not filtered_console_errors and not page_errors and not filtered_http_errors:
            return
        details = filtered_console_errors + page_errors + filtered_http_errors
        pytest.fail(f"{context} recorded browser errors: {' | '.join(details[:10])}")

    def _on_console(self, message) -> None:
        if message.type == "error":
            self.console_errors.append(f"console:{message.text}")

    def _on_pageerror(self, error) -> None:
        self.page_errors.append(f"pageerror:{error}")

    def _on_response(self, response) -> None:
        url = normalize_localhost(response.url)
        if not url.startswith(self._origin):
            return
        if response.status < 400:
            return
        self.http_errors.append(f"http:{response.status}:{response.request.method}:{url}")


class ForensicScreenshots:
    def __init__(self, root_dir: Path, test_id: str) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.test_id = slugify(test_id)
        self.paths: list[Path] = []
        self._counter = 0

    def capture(self, page: Page, label: str) -> Path:
        self._counter += 1
        filename = f"{self.test_id}-{self._counter:02d}-{slugify(label)}.png"
        path = self.root_dir / filename
        page.screenshot(path=str(path), full_page=True)
        self.paths.append(path)
        return path


class AdminApi:
    def __init__(self, api_base_url: str, api_key: str, timeout_s: float) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.client = httpx.Client(
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout_s,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "AdminApi":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def list_users(self, query: str | None = None) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.api_base_url}/api/v1/users", params={"limit": 500, "q": query or None})
        response.raise_for_status()
        return response.json().get("items", [])

    def wait_for_user_id(self, username: str, timeout_s: float) -> int:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for item in self.list_users(username):
                if item.get("username") == username:
                    return int(item["id"])
            time.sleep(0.5)
        pytest.fail(f"Timed out waiting for user {username}")

    def get_user(self, user_id: int) -> dict[str, Any]:
        response = self.client.get(f"{self.api_base_url}/api/v1/users/{user_id}")
        response.raise_for_status()
        return response.json()

    def delete_user(self, user_id: int) -> None:
        self.client.delete(f"{self.api_base_url}/api/v1/users/{user_id}")

    def list_groups(self) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.api_base_url}/api/v1/groups", params={"enabled_only": "false"})
        response.raise_for_status()
        return response.json().get("items", [])

    def wait_for_group_id(self, group_name: str, timeout_s: float) -> int:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for item in self.list_groups():
                if item.get("name") == group_name:
                    return int(item["id"])
            time.sleep(0.5)
        pytest.fail(f"Timed out waiting for group {group_name}")

    def get_group_members(self, group_id: int) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.api_base_url}/api/v1/groups/{group_id}/members")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else payload.get("items", [])

    def delete_group(self, group_id: int) -> None:
        self.client.delete(f"{self.api_base_url}/api/v1/groups/{group_id}")

    def list_channels(self) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.api_base_url}/channels")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else payload.get("items", [])

    def wait_for_channel_id(self, channel_name: str, timeout_s: float) -> int:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for item in self.list_channels():
                if item.get("name") == channel_name:
                    return int(item["id"])
            time.sleep(0.5)
        pytest.fail(f"Timed out waiting for channel {channel_name}")

    def create_channel(self, payload: dict[str, Any]) -> int:
        response = self.client.post(f"{self.api_base_url}/channels", json=payload)
        response.raise_for_status()
        data = response.json()
        return int(data.get("id"))

    def delete_channel(self, channel_id: int) -> None:
        self.client.delete(f"{self.api_base_url}/channels/{channel_id}")

    def create_prompt(self, payload: dict[str, Any]) -> int:
        response = self.client.post(f"{self.api_base_url}/prompts", json=payload)
        response.raise_for_status()
        data = response.json()
        return int(data.get("id") or data.get("prompt_id"))

    def list_api_keys(self) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.api_base_url}/admin/api-keys")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else payload.get("items", [])

    def list_prompts(self) -> list[dict[str, Any]]:
        response = self.client.get(f"{self.api_base_url}/prompts")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else payload.get("items", [])

    def delete_prompt(self, prompt_id: int) -> None:
        self.client.delete(f"{self.api_base_url}/prompts/{prompt_id}")

    def create_message(self, payload: dict[str, Any]) -> int:
        response = self.client.post(f"{self.api_base_url}/messages", json=payload)
        response.raise_for_status()
        data = response.json()
        return int(data.get("id") or data.get("message_id"))

    def wait_for_message(self, message_id: int, timeout_s: float) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            response = self.client.get(f"{self.api_base_url}/messages/{message_id}")
            if response.status_code == 200:
                return response.json()
            time.sleep(0.5)
        pytest.fail(f"Timed out waiting for message {message_id}")

    def wait_for_deliveries(self, message_id: int, timeout_s: float) -> list[dict[str, Any]]:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            response = self.client.get(f"{self.api_base_url}/messages/{message_id}/deliveries")
            if response.status_code == 200:
                payload = response.json()
                items = payload if isinstance(payload, list) else payload.get("items", [])
                if items:
                    return items
            time.sleep(1.0)
        pytest.fail(f"Timed out waiting for deliveries for message {message_id}")

    def delete_message(self, message_id: int) -> None:
        self.client.delete(f"{self.api_base_url}/messages/{message_id}")


def extract_message_id_from_status(text: str) -> int:
    match = re.search(r"Created message (\d+)", text)
    if not match:
        pytest.fail(f"Could not extract message id from status text: {text}")
    return int(match.group(1))
