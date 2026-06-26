#!/usr/bin/env python3

from __future__ import annotations

import time

import pytest

from tests.application.webui_e2e_support import (
    AdminApi,
    api_timeout_s,
    login_via_browser,
    managed_page,
    normalize_localhost,
    page_timeout_ms,
    require_value,
    submit_entity_form,
    wait_until,
    wait_for_heading,
    wait_for_text,
)


pytestmark = [pytest.mark.application, pytest.mark.no_llm_dependency]


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


def test_webui_t9_prompt_management_crud(test_config):
    base_url = normalize_localhost(require_value(test_config, "web_server.base_url").rstrip("/"))
    api_base_url = normalize_localhost(require_value(test_config, "api_server.base_url").rstrip("/"))
    api_key = require_value(test_config, "api_server.api_key")
    username = require_value(test_config, "web_server.username")
    password = require_value(test_config, "web_server.password")
    timeout_ms = page_timeout_ms(test_config)
    timeout_s = api_timeout_s(test_config)
    suffix = str(int(time.time()))
    prompt_name = f"e2e_prompt_{suffix}"
    updated_name = f"{prompt_name}_updated"
    prompt_id: int | None = None

    with AdminApi(api_base_url, api_key, timeout_s) as api:
        try:
            with managed_page("w28a-442-prompt-management", timeout_ms) as page:
                login_via_browser(page, base_url, username, password, timeout_ms)
                page.get_by_role("link", name="Prompts").click()
                wait_for_heading(page, "Prompts", timeout_ms)

                page.get_by_role("button", name="Add prompt").click()
                page.fill("#ef-name", prompt_name)
                page.select_option("#ef-channel_type", "email")
                page.fill("#ef-language", "en")
                page.fill("#ef-keyword", "formal")
                page.fill("#ef-priority", "15")
                page.fill("#prompts-variables-json-adopted", '{"tone":"formal"}')
                page.fill("#prompts-text-adopted", f"Prompt text {suffix}")
                page.get_by_role("button", name="Save").click()

                wait_for_text(page, f"Created prompt {prompt_name}.", timeout_ms)
                prompt_payload = wait_until(
                    lambda: next((item for item in api.list_prompts() if item.get("name") == prompt_name), None),
                    timeout_s,
                    f"created prompt {prompt_name}",
                )
                prompt_id = int(prompt_payload["id"])
                prompt_row = _prompt_row(page, prompt_name, timeout_s)
                assert "formal" in prompt_row.inner_text().lower()

                prompt_row.get_by_role("button", name="Edit").click()
                page.fill("#ef-name", updated_name)
                page.fill("#ef-priority", "25")
                page.fill("#prompts-variables-json-adopted", '{"tone":"strict"}')
                page.fill("#prompts-text-adopted", f"Updated prompt text {suffix}")
                submit_entity_form(page)

                wait_for_text(page, "Updated prompt", timeout_ms)
                updated_prompt = wait_until(
                    lambda: next(
                        (
                            item
                            for item in api.list_prompts()
                            if int(item.get("id")) == prompt_id
                            and item.get("name") == updated_name
                            and str(item.get("priority")) == "25"
                            and item.get("prompt_text") == f"Updated prompt text {suffix}"
                        ),
                        None,
                    ),
                    timeout_s,
                    f"updated prompt {prompt_id}",
                )
                assert updated_prompt["name"] == updated_name
                assert str(updated_prompt.get("priority")) == "25"
                assert int(updated_prompt.get("enabled") or 0) == 1
                assert updated_prompt["prompt_text"] == f"Updated prompt text {suffix}"

                page.once("dialog", lambda dialog: dialog.accept())
                _prompt_row(page, updated_name, timeout_s).get_by_role("button", name="Delete").click()
                wait_for_text(page, "Deleted 1 prompt.", timeout_ms)
                wait_until(
                    lambda: not any(int(item.get("id")) == prompt_id for item in api.list_prompts()),
                    timeout_s,
                    f"deleted prompt {prompt_id}",
                )
                wait_until(
                    lambda: page.locator("tr", has_text=updated_name).count() == 0,
                    timeout_s,
                    f"prompt row {updated_name} to disappear",
                )
                assert page.locator("tr", has_text=updated_name).count() == 0
                prompt_id = None
        finally:
            if prompt_id is not None:
                api.delete_prompt(prompt_id)
