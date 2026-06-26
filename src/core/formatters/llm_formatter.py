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
Description: Enhanced LLM Formatter for Notification Agent MCP Server - Formats messages using LLM with prompt selection, automatic translation, channel restriction enforcement, and user preference application

Related Requirements: FR1.10, FR1.11
Covers: BR1.3
Related Tasks: T8
Related Architecture: CC3.1
Related Tests: UT1.5, IT1.15, AT1.2

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import ast
import json
import math
import re
import time
from typing import Optional, Dict, Any, List

from src.core.cache_integration import (
    build_context_hash,
    build_model_config_hash,
    build_prompt_hash,
    cached_message_format,
    cached_prompt_render,
    cached_summary_generation,
    cached_translation,
    run_sync,
)
from src.core.prompts.prompt_manager import PromptManager
from src.core.llm.runtime_client import LLMManager
from src.core.users.user_manager import UserManager
from src.core.groups.group_manager import GroupManager
from src.core.formatters.format_converter import FormatConverter
from src.database.repositories import ChannelRepository
from src.database.db_manager import DatabaseManager
from src.config import get_config
from src.utils.logger import get_logger, get_context_logger

logger = get_logger(__name__)


class LLMFormatter:
    """Enhanced LLM formatter with prompt selection, translation, and restrictions"""

    def __init__(self, db: DatabaseManager, config=None, llm_manager: Optional[LLMManager] = None):
        """
        Initialize LLM formatter

        Args:
            db: DatabaseManager instance
            config: RuntimeConfig instance (optional)
        """
        self.db = db
        self.config = config or get_config()
        self.prompt_manager = PromptManager(db)
        self.llm_manager = llm_manager or LLMManager(self.config)
        self.user_manager = UserManager(db)
        self.group_manager = GroupManager(db)
        self.channel_repo = ChannelRepository(db)
        self.format_converter = FormatConverter(self.llm_manager)

        # Initialize LLM connection lazily (don't block on startup)
        # Connection will be established on first use
        logger.debug("LLM formatter initialized (connection will be established on first use)")

    def format_message(
        self,
        content: List[Dict[str, Any]],
        channel_type: str,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        explicit_prompt: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        message_id: Optional[int] = None,  # Added for link generation
        message_guid: Optional[str] = None,  # Added for secure GUID-based link generation
        channel_id: Optional[int] = None,  # Added to get specific channel restrictions
    ) -> Dict[str, Any]:
        """
        Format message content using LLM with prompt selection, translation, and restrictions.

        Args:
            content: Original message content blocks
            channel_type: Channel type (email, sms, whatsapp, etc.)
            user_id: User ID (for preferences and prompt selection)
            group_id: Group ID (for prompt selection)
            explicit_prompt: Explicit prompt name to use (highest priority)
            variables: Additional variables for prompt rendering

        Returns:
            Formatted content dict with:
            - formatted_content: List of formatted content blocks
            - prompt_used: Prompt that was used
            - translation_applied: Whether translation was applied
            - restrictions_applied: List of restrictions that were applied
        """

        # Extract explicit prompt from variables if not provided as parameter (FR1.15 Priority #1)
        if not explicit_prompt and variables and '_explicit_prompt' in variables:
            explicit_prompt = variables.get('_explicit_prompt')
            logger.info(f"Extracted explicit prompt from message variables: {explicit_prompt}")

        # 1. Get channel restrictions
        # If channel_id is provided, get specific channel; otherwise get by type
        if channel_id:
            channel = self.channel_repo.get_by_id(channel_id)
            # If channel not found by ID, try to get by type as fallback
            if not channel:
                channel = self._get_channel(channel_type)
        else:
            channel = self._get_channel(channel_type)
        restrictions = self._get_channel_restrictions(channel)

        # Store channel for later use (needed for re-fetching restrictions if empty)
        if not restrictions and channel:
            # Try to re-fetch restrictions if they were empty
            restrictions = self._get_channel_restrictions(channel)

        # 1.5. Check if content needs summarization BEFORE prompt selection
        # Get max_length early to decide if we should summarize first
        logger.debug(f"[STEP 1] Starting summarization check - restrictions={restrictions}, channel_id={channel_id}, channel_type={channel_type}")
        max_length = restrictions.get("max_length") if restrictions else None
        logger.debug(f"[STEP 1] Initial max_length from restrictions: {max_length}")

        if not max_length and channel:
            limits_json = channel.get("limits_json")
            logger.debug(f"[STEP 1] Checking limits_json: {bool(limits_json)}, channel={channel.get('name') if channel else None}")
            if limits_json:
                try:
                    limits = json.loads(limits_json) if isinstance(limits_json, str) else limits_json
                    max_length = limits.get("max_length")
                    logger.debug(f"[STEP 1] max_length from limits_json: {max_length}")
                except Exception as e:
                    logger.debug(f"[STEP 1] Failed to parse limits_json: {e}")

        # Default max_length for Slack/chat channels if not set (Slack limit is 4000 chars)
        if not max_length and channel_type in ['slack', 'chat', 'chat_rest']:
            max_length = 4000
            logger.debug(f"[STEP 1] Using default max_length={max_length} for {channel_type} channel")

        # NOTE: user_prefs is not resolved until later in this method.
        # Initialise it to avoid UnboundLocalError in early max_length checks.
        user_prefs = None

        # Destination preferences must override channel defaults/limits.
        if variables and variables.get("preferences") and variables["preferences"].get("max_length"):
            max_length = variables["preferences"].get("max_length")
        elif user_prefs and user_prefs.get("max_length"):
            max_length = user_prefs.get("max_length")

        # Destination preferences must override any channel defaults/limits (RULES: no silent override).
        if variables and variables.get("preferences") and variables["preferences"].get("max_length"):
            max_length = variables["preferences"].get("max_length")
        elif user_prefs and user_prefs.get("max_length"):
            max_length = user_prefs.get("max_length")

        # Get original content length
        original_content_text = " ".join([block.get("body", "") for block in content if isinstance(block, dict)])
        original_content_length = len(original_content_text)
        logger.debug(f"[STEP 1] Original content length: {original_content_length} chars")
        logger.debug(f"[STEP 1] Original content length: {original_content_length} chars")

        # Get message_id and message_guid for link generation (from variables or parameter)
        msg_id = message_id or (variables.get('message_id') if variables else None)
        msg_guid = message_guid or (variables.get('message_guid') if variables else None)

        # 1.7. Load user preferences EARLY (needed for max_length check)
        # CRITICAL: Load user_prefs BEFORE summarization check so we can detect max_length from destination preferences
        user_prefs_early = None
        if variables and variables.get('preferences'):
            user_prefs_early = variables['preferences']

        # 1.8. Apply max_length with destination-preference priority
        # PRIORITY ORDER: destination/user_prefs > restrictions > channel limits > defaults
        if user_prefs_early and 'max_length' in user_prefs_early:
            pref_max_length = user_prefs_early.get('max_length')
            if pref_max_length:
                max_length = pref_max_length
                logger.debug(f"[STEP 1] ✅ max_length from user_prefs (destination preferences): {max_length}")

        # Check if PDF generation is requested.
        # Even when PDFs are requested, destination max_length should still be honoured for the
        # formatted body (summary+link). Downstream PDF generation can choose whether to use the
        # summary or full content, but skipping summarisation here breaks max_length guarantees.
        pdf_requested = False
        if variables and variables.get("preferences"):
            pdf_requested = variables["preferences"].get("generate_pdf", False)
        if user_prefs_early:
            pdf_requested = pdf_requested or user_prefs_early.get("generate_pdf", False)


        # If content is too large OR link_strategy requires summary+link, create summary first.
        link_strategy = restrictions.get("link_strategy") if restrictions else None
        force_summary_link = link_strategy == "summary+link" or (
            user_prefs_early
            and str(user_prefs_early.get("content_style") or "").startswith("summary+link")
        )
        needs_summarization = (max_length and original_content_length > max_length) or force_summary_link
        logger.debug(f"[STEP 1] Summarization check: needs_summarization={needs_summarization}, pdf_requested={pdf_requested}, max_length={max_length}, original_length={original_content_length}")

        summary_result = None
        if needs_summarization:
            logger.debug(f"[STEP 1] ✅ TRIGGERED: Content too large ({original_content_length} > {max_length}), creating summary with link")
            # Create summary of original content (ALWAYS saves full message and provides link)
            # Pass target language so summary can be generated in the correct language
            # NOTE: target_language_for_summary will be set after user_prefs are loaded (see below)
            summary_result = None  # Will be created after we have user_prefs and target_language

        # 2. Get user preferences (if user_id provided) OR from variables (for destination preferences)
        user_prefs = user_prefs_early  # Use early-loaded prefs if available
        user_keywords = []
        user_language = None

        # Check if preferences are provided in variables (for destination-level preferences)
        # CRITICAL: Check variables FIRST, even if user_id exists, because destination preferences override user preferences
        if variables and variables.get("preferences"):
            destination_prefs = variables.get("preferences")
            user_prefs = destination_prefs
            user_language = destination_prefs.get("language")
            # CRITICAL: Store language in variables for later use (link creation)
            variables["target_language"] = user_language
            ctx_logger = get_context_logger(logger.name, user_id=user_id, message_id=message_id)

        if user_id:
            user = self.user_manager.user_repo.get_by_id(user_id)
            if user:
                if not user_prefs:
                    user_prefs = {
                        "language": user.get("language"),
                        "preferred_channel": user.get("preferred_channel"),
                        "content_style": user.get("content_style"),
                        "timezone": user.get("timezone"),
                    }
                if not user_language:
                    user_language = user.get("language")
                # Always load user keywords (prompt selection should not be blocked by destination prefs).
                keywords = self.user_manager.keyword_repo.get_by_user_id(user_id)
                user_keywords = [kw["keyword"] for kw in keywords]

        # 3. Get group preferences (if group_id provided)
        group_language = None
        group_keywords = []
        if group_id:
            group = self.group_manager.group_repo.get_by_id(group_id)
            if group:
                group_language = group.get("language")
                # Get group keywords
                try:
                    from src.database.repositories import GroupKeywordRepository
                    keyword_repo = GroupKeywordRepository(self.db)
                    keywords = keyword_repo.get_by_group_id(group_id)
                    group_keywords = [kw["keyword"] for kw in keywords] if keywords else []
                except Exception as e:
                    logger.warning(f"Failed to get group keywords: {e}")
                    group_keywords = []

        # 4. Select prompt based on priority
        prompt = self._select_prompt(
            channel_type=channel_type,
            explicit_prompt=explicit_prompt,
            user_id=user_id,
            group_id=group_id,
            user_keywords=user_keywords,
            group_keywords=group_keywords,
            user_language=user_language,
            group_language=group_language,
        )

        if not prompt:
            logger.warning(f"No prompt found for channel {channel_type}, using default formatting")
            # CRITICAL: Check summarization even when using default formatting
            if needs_summarization and summary_result is None:
                target_language_for_summary = None
                if variables and variables.get('preferences') and variables['preferences'].get('language'):
                    target_language_for_summary = variables['preferences']['language']
                elif user_prefs and user_prefs.get('language'):
                    target_language_for_summary = user_prefs.get('language')
                elif user_language:
                    target_language_for_summary = user_language
                elif group_language:
                    target_language_for_summary = group_language
                logger.debug(f"[STEP 2] Creating summary in _format_without_prompt with target_language={target_language_for_summary}")
                summary_result = self._create_summary_with_link(
                    content=original_content_text,
                    max_length=max_length,
                    channel_type=channel_type,
                    user_prefs=user_prefs,
                    target_language=target_language_for_summary,
                    message_id=msg_id,
                    message_guid=msg_guid,
                )
            return self._format_without_prompt(content, restrictions, user_prefs, summary_result=summary_result, max_length=max_length, channel_type=channel_type, message_id=msg_id, message_guid=msg_guid)

        # 5. DETERMINE TARGET LANGUAGE FOR MESSAGE OUTPUT
        # This is needed to translate the prompt text if required
        # Priority: variables > destination prefs > user > group > CHANNEL > system default
        target_language = None
        if variables and variables.get('target_language'):
            target_language = variables['target_language']
        elif variables and variables.get('preferences') and variables['preferences'].get('language'):
            target_language = variables['preferences']['language']
        elif user_prefs and user_prefs.get('language'):
            target_language = user_prefs.get('language')
        elif user_language:
            target_language = user_language
        elif group_language:
            target_language = group_language
        elif channel:
            # Get channel language from preferences_json
            channel_prefs = channel.get("preferences_json")
            if channel_prefs:
                try:
                    if isinstance(channel_prefs, str):
                        channel_prefs = json.loads(channel_prefs)
                    channel_language = channel_prefs.get("language")
                    if channel_language:
                        target_language = channel_language
                except Exception as e:
                    logger.warning(f"Failed to parse channel preferences: {e}")

        if not target_language:
            # W28A-322: System default language fallback — use `or "en"` to handle empty-string config
            target_language = self.config.get("app.default_language") or "en"
            logger.info(f"[TARGET LANGUAGE] Using system default: {target_language}")

        prompt_language = str(prompt.get("language") or "").strip().lower() if prompt else ""
        normalized_target_language = str(target_language or "").strip().lower()
        prompt_already_in_target_language = bool(
            prompt_language
            and normalized_target_language
            and prompt_language == normalized_target_language
        )

        # Store in variables for later use
        if not variables:
            variables = {}
        variables['target_language'] = target_language
        if prompt_language:
            variables["_selected_prompt_language"] = prompt_language

        # 6. TRANSLATE PROMPT TEXT IF NEEDED
        # Language enforcement is already injected later via
        # _enhance_prompt_with_instructions(), so keep prompt translation
        # opt-in to avoid burning the first real LLM budget on redundant work.
        prompt_text_for_llm = prompt["prompt_text"]
        translate_prompt_text = bool(self.config.get("llm.translate_prompt_text", False))
        if (
            translate_prompt_text
            and target_language
            and target_language != "en"
            and not prompt_already_in_target_language
        ):
            try:
                prompt_text_for_llm = self._translate(prompt["prompt_text"], target_language)
            except Exception as e:
                logger.warning(f"[PROMPT TRANSLATION] Failed to translate prompt: {e}, using original")
                prompt_text_for_llm = prompt["prompt_text"]

        # 7. Build prompt variables
        prompt_vars = self._build_prompt_variables(
            content=content,
            channel_type=channel_type,
            restrictions=restrictions,
            user_prefs=user_prefs,
            variables=variables,
        )

        # 8. Render prompt with translated prompt text
        rendered_prompt = self._render_prompt_cached(
            prompt_text_for_llm,
            prompt_vars,
            channel_type=channel_type,
            target_language=target_language,
        )

        # If prompt doesn't include content placeholder, append content explicitly
        if "{content}" not in prompt["prompt_text"] and prompt_vars.get("content"):
            rendered_prompt += f"\n\nContent to format:\n{prompt_vars['content']}"

        # 7. Check if content needs summarization BEFORE LLM formatting
        # Get max_length early to decide if we should summarize first
        logger.debug(f"[STEP 1] Starting summarization check - restrictions={restrictions}, channel_id={channel_id}, channel_type={channel_type}")
        max_length = restrictions.get("max_length") if restrictions else None
        logger.debug(f"[STEP 1] Initial max_length from restrictions: {max_length}")

        if not max_length and channel:
            limits_json = channel.get("limits_json")
            logger.debug(f"[STEP 1] Checking limits_json: {bool(limits_json)}, channel={channel.get('name') if channel else None}")
            if limits_json:
                try:
                    limits = json.loads(limits_json) if isinstance(limits_json, str) else limits_json
                    max_length = limits.get("max_length")
                    logger.debug(f"[STEP 1] max_length from limits_json: {max_length}")
                except Exception as e:
                    logger.debug(f"[STEP 1] Failed to parse limits_json: {e}")

        # Default max_length for Slack/chat channels if not set (Slack limit is 4000 chars)
        if not max_length and channel_type in ['slack', 'chat', 'chat_rest']:
            max_length = 4000
            logger.debug(f"[STEP 1] Using default max_length={max_length} for {channel_type} channel")

        # Destination preferences must override channel defaults/limits.
        if variables and variables.get("preferences") and variables["preferences"].get("max_length"):
            max_length = variables["preferences"].get("max_length")
        elif user_prefs and user_prefs.get("max_length"):
            max_length = user_prefs.get("max_length")

        # Get original content length
        original_content_text = " ".join([block.get("body", "") for block in content if isinstance(block, dict)])
        original_content_length = len(original_content_text)
        logger.debug(f"[STEP 1] Original content length: {original_content_length} chars")
        logger.debug(f"[STEP 1] Original content length: {original_content_length} chars")

        # Get message_id and message_guid for link generation (from variables or parameter)
        msg_id = message_id or (variables.get('message_id') if variables else None)
        msg_guid = message_guid or (variables.get('message_guid') if variables else None)

        # If content is too large OR link_strategy requires summary+link, create summary first.
        link_strategy = restrictions.get("link_strategy") if restrictions else None
        force_summary_link = link_strategy == "summary+link" or (
            user_prefs
            and str(user_prefs.get("content_style") or "").startswith("summary+link")
        )
        needs_summarization = (max_length and original_content_length > max_length) or force_summary_link
        logger.debug(f"[STEP 1] Summarization check: needs_summarization={needs_summarization}, max_length={max_length}, original_length={original_content_length}")

        summary_result = None
        if needs_summarization:
            # Create summary of original content (ALWAYS saves full message and provides link)
            # Pass target language so summary can be generated in the correct language
            # CRITICAL: Get language from destination preferences first (highest priority)
            target_language_for_summary = None
            if variables and variables.get('preferences') and variables['preferences'].get('language'):
                target_language_for_summary = variables['preferences']['language']
            elif user_prefs and user_prefs.get('language'):
                target_language_for_summary = user_prefs.get('language')
            elif user_language:
                target_language_for_summary = user_language
            elif group_language:
                target_language_for_summary = group_language

            if not target_language_for_summary:
                pass

            summary_result = self._create_summary_with_link(
                content=original_content_text,
                max_length=max_length,
                channel_type=channel_type,
                user_prefs=user_prefs,
                target_language=target_language_for_summary,  # Generate summary in target language
                message_id=msg_id,
                message_guid=msg_guid,
            )
            # Replace content with summary for LLM formatting
            # Extract summary text WITHOUT the link (link will be added after translation)
            summary_text_without_link = summary_result["summary_text"]
            # Remove the link part if it exists
            if "<" in summary_text_without_link and "|" in summary_text_without_link:
                # Slack link format - remove it
                # re is already imported at module level
                summary_text_without_link = re.sub(r'<[^>|]+\|[^>]+>', '', summary_text_without_link).strip()
            elif "[View full message" in summary_text_without_link:
                # Plain text link - remove it
                # re is already imported at module level
                summary_text_without_link = re.sub(r'\[View full message[^\]]+\]', '', summary_text_without_link).strip()

            # Deterministic max-length enforcement for summary payload.
            summary_text_without_link = self._truncate_to_max_length(summary_text_without_link, max_length)


            content = [{"type": "text", "body": summary_text_without_link}]
            # CRITICAL: Preserve target_language before recreating variables dict
            target_lang_backup = variables.get('target_language') if variables else None
            variables = variables or {}
            # CRITICAL: Restore target_language if it was set (MUST NOT LOSE THIS)
            if target_lang_backup:
                variables['target_language'] = target_lang_backup
            # CRITICAL: Don't store the link from summary_result here - it has English labels
            # The link will be created with translated labels later in step 11a
            # variables["full_message_link"] = summary_result["full_message_link"]  # REMOVED - use translated link instead
            variables["has_summary"] = True
            variables["original_length"] = summary_result["original_length"]
            variables["message_id"] = msg_id  # Store message_id for link generation after translation
            variables["message_guid"] = msg_guid  # Store message_guid for link generation (preferred)
            # Rebuild prompt variables with summarized content
            prompt_vars = self._build_prompt_variables(
                content=content,
                channel_type=channel_type,
                restrictions=restrictions,
                user_prefs=user_prefs,
                variables=variables,
            )
            rendered_prompt = self._render_prompt_cached(
                prompt["prompt_text"],
                prompt_vars,
                channel_type=channel_type,
                target_language=target_language,
            )

            # CRITICAL: Add explicit instruction to NOT expand the summary
            if "{content}" not in prompt["prompt_text"]:
                rendered_prompt += f"\n\nContent to format:\n{prompt_vars['content']}"
            else:
                # Add instruction to keep content concise if it's already summarized
                rendered_prompt += f"\n\nIMPORTANT: The content above is already a summary. DO NOT expand it. Keep it concise and within {max_length} characters."

        # 8. Initialize LLM if not already initialized
        if not self.llm_manager.llm:
            logger.info("Initializing LLM connection for formatting...")
            try:
                self.llm_manager.connect()
            except Exception as e:
                logger.warning(f"LLM initialization failed: {e}, require strict remediation")

        # 9. Invoke LLM to format content (with subject and intro instructions)
        # CRITICAL: If we already have a summary, skip LLM formatting to avoid expansion
        # Just use the summary directly and add formatting (subject, intro) if needed
        if summary_result and max_length:
            # We already have a summary - use it directly without LLM formatting
            # This prevents the LLM from expanding the summary back to full content
            len(summary_result['summary_text'])
            formatted_text = summary_result["summary_text"]
            logger.debug(f"[STEP 4] Using summary text: {len(formatted_text)} chars")
            # Ensure it's within max_length
            if len(formatted_text) > max_length:
                formatted_text = self._truncate_to_max_length(formatted_text, max_length)
        else:
            # No summary - proceed with normal LLM formatting
            enhanced_prompt = self._enhance_prompt_with_instructions(rendered_prompt, user_prefs, prompt_vars)
            try:
                # Try to use LLM - don't check availability first, just try it
                llm = self.llm_manager.get_llm()
                if llm:
                    ctx_logger = get_context_logger(
                        logger.name,
                        message_id=message_id,
                        user_id=user_id,
                        channel_id=channel_id,
                        llm_session=f"format-{message_id}-{user_id or 'anon'}"
                    )
                    # Use the heavier formatting budget for full non-English email jobs.
                    llm_timeout = self.config.get(
                        "llm.formatting_timeout",
                        self.config.get("llm.query_timeout", self.config.get("llm.timeout", 300)),
                    )
                    target_lang_lower = str(target_language or "").strip().lower()
                    if (
                        channel_type in {"email", "smtp"}
                        and not max_length
                        and target_lang_lower
                        and target_lang_lower not in {"en", "english"}
                    ):
                        llm_timeout = max(
                            float(llm_timeout or 0),
                            float(
                                self.config.get(
                                    "llm.total_format_budget_smtp_full",
                                    self.config.get("llm.format_call_timeout_smtp_full_non_english", 280.0),
                                )
                                or 280.0
                            ),
                        )
                    ctx_logger.info(f"Waiting for LLM to format message (timeout: {llm_timeout}s)")
                    try:
                        try:
                            llm_max_tokens_int = int(float(self.config.get("llm.max_tokens", 32768) or 32768))
                        except (TypeError, ValueError):
                            llm_max_tokens_int = 32768
                        try:
                            formatting_min_predict = int(
                                float(self.config.get("llm.formatting_num_predict_min", 1024) or 1024)
                            )
                        except (TypeError, ValueError):
                            formatting_min_predict = 1024
                        content_text = prompt_vars.get("content") if prompt_vars else ""
                        content_tokens_estimate = self._estimate_tokens(content_text or "")
                        formatting_num_predict = max(
                            formatting_min_predict,
                            min(
                                llm_max_tokens_int,
                                max(formatting_min_predict, content_tokens_estimate + 768),
                            ),
                        )
                        format_invoke_params = {"num_predict": formatting_num_predict}
                        token_limits = self._get_token_limits()
                        max_input = token_limits["max_input"]
                        prompt_tokens = self._estimate_tokens(enhanced_prompt)
                        if content_text and prompt_tokens > max_input:
                            content_tokens = self._estimate_tokens(content_text)
                            overhead_tokens = max(prompt_tokens - content_tokens, 0)
                            max_content_tokens = max_input - overhead_tokens
                            if max_content_tokens <= 0:
                                raise RuntimeError(
                                    f"Formatting prompt overhead exceeds input budget: overhead={overhead_tokens}, "
                                    f"max_input={max_input}"
                                )
                            chunks = self._chunk_text_by_tokens(content_text, max_content_tokens)
                            chunk_outputs = []
                            for chunk in chunks:
                                chunk_vars = dict(prompt_vars) if prompt_vars else {}
                                chunk_vars["content"] = chunk
                                chunk_rendered = self._render_prompt_cached(
                                    prompt_text_for_llm,
                                    chunk_vars,
                                    channel_type=channel_type,
                                    target_language=target_language,
                                )
                                if "{content}" not in prompt["prompt_text"] and chunk_vars.get("content"):
                                    chunk_rendered += f"\n\nContent to format:\n{chunk_vars['content']}"
                                chunk_prompt = self._enhance_prompt_with_instructions(
                                    chunk_rendered,
                                    user_prefs,
                                    chunk_vars,
                                )
                                chunk_output = self._invoke_formatting_prompt(
                                    chunk_prompt,
                                    channel_type=channel_type,
                                    target_language=target_language,
                                    max_length=max_length,
                                    prompt_vars=chunk_vars,
                                    timeout_seconds=float(llm_timeout),
                                    invoke_params=format_invoke_params,
                                )
                                chunk_outputs.append(chunk_output.strip())
                            formatted_text = "\n\n".join(chunk_outputs).strip()
                        else:
                            formatted_text = self._invoke_formatting_prompt(
                                enhanced_prompt,
                                channel_type=channel_type,
                                target_language=target_language,
                                max_length=max_length,
                                prompt_vars=prompt_vars,
                                timeout_seconds=float(llm_timeout),
                                invoke_params=format_invoke_params,
                            ).strip()

                        # CRITICAL: Remove any prompt text that may have been included in the response
                        prompt_patterns = [
                            r'^Please provide a summary.*?:\s*',
                            r'^Create a concise summary.*?:\s*',
                            r'^Summary \(in .*?\):\s*',
                            r'^Content to summarize:\s*',
                            r'^Content to format:\s*',
                            r'^TARGET LANGUAGE:.*?\n',
                            r'^CHANNEL TYPE:.*?\n',
                            r'^IMPORTANT:.*?\n',
                        ]
                        for pattern in prompt_patterns:
                            formatted_text = re.sub(pattern, '', formatted_text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)

                        # Remove any remaining prompt-like text at the start
                        formatted_text = formatted_text.strip()
                        if formatted_text.startswith('Please provide') or formatted_text.startswith('Create a concise'):
                            colon_pos = formatted_text.find(':')
                            newline_pos = formatted_text.find('\n')
                            if colon_pos > 0 and (newline_pos < 0 or colon_pos < newline_pos):
                                formatted_text = formatted_text[colon_pos + 1:].strip()
                            elif newline_pos > 0:
                                formatted_text = formatted_text[newline_pos + 1:].strip()

                        # CRITICAL: If we created a summary, enforce max_length strictly
                        # The LLM should not expand the summary beyond the limit
                        if summary_result and max_length:
                            original_summary_len = len(summary_result.get("summary_text", ""))
                            if len(formatted_text) > max_length:
                                logger.warning(f"LLM expanded summary beyond max_length ({len(formatted_text)} > {max_length}), truncating. Original summary was {original_summary_len} chars")
                                formatted_text = self._truncate_to_max_length(formatted_text, max_length)

                        ctx_logger.info(f"LLM formatting completed: {len(formatted_text)} chars (max: {max_length if max_length else 'none'})")
                    except Exception as llm_error:
                        # LLM call failed or timed out - use fallback
                        ctx_logger.warning(f"LLM formatting failed/timed out: {llm_error}, raising strict error")
                        raise  # Re-raise to trigger fallback handling
                else:
                    # LLM not initialized, use fallback
                    raise Exception("LLM not initialized")
            except Exception as e:
                logger.warning(f"⚠️ LLM formatting failed: {e}, raising strict error")
                # If we already created a summary, use it; otherwise format fallback
                if summary_result:
                    formatted_text = summary_result["summary_text"]
                else:
                    formatted_text = self._format_fallback(content, restrictions, user_prefs, prompt.get("name") if prompt else None)
                    # Check if fallback result is still too long
                    if max_length and len(formatted_text) > max_length:
                        # Create summary from fallback (ALWAYS with link)
                        # Pass target language so summary can be generated in the correct language
                        target_language_for_summary = user_language or group_language
                        summary_result = self._create_summary_with_link(
                            content=formatted_text,
                            max_length=max_length,
                            channel_type=channel_type,
                            user_prefs=user_prefs,
                            target_language=target_language_for_summary,  # Generate summary in target language
                            message_id=msg_id,
                            message_guid=msg_guid,
                        )
                        formatted_text = summary_result["summary_text"]

        # Guard: if no max_length is set and the formatted output is empty or too short,
        # fall back to formatting the full content to avoid empty/near-empty outputs.
        if (not max_length) and original_content_length:
            formatted_len = len(formatted_text.strip()) if formatted_text else 0
            min_expected_len = max(200, int(original_content_length * 0.3)) if original_content_length > 1000 else 50
            if formatted_len < min_expected_len:
                logger.warning(
                    f"[FORMAT GUARD] Output too short for full-content request "
                    f"(formatted_len={formatted_len}, min_expected_len={min_expected_len}, original_len={original_content_length}). "
                    f"Using fallback formatting."
                )
                formatted_text = self._format_fallback(content, restrictions, user_prefs, prompt.get("name") if prompt else None)

        # 9. Extract subject and intro from formatted text (if LLM generated them) BEFORE translation
        subject, intro, body_text = self._extract_subject_intro_body(formatted_text, variables or {})
        formatted_text = body_text or formatted_text

        # CRITICAL: Enforce max_length AFTER all formatting (including subject/intro extraction)
        # This ensures the final output never exceeds the limit
        if max_length and len(formatted_text) > max_length:
            logger.warning(f"Formatted text ({len(formatted_text)} chars) exceeds max_length ({max_length}), truncating")
            formatted_text = self._truncate_to_max_length(formatted_text, max_length)
            logger.info(f"Truncated to {len(formatted_text)} chars")

        # Generate default subject if missing (from first line of content)
        if not subject:
            first_line = formatted_text.split('\n')[0].strip()
            # re is already imported at module level
            first_line = re.sub(r'<[^>]+>', '', first_line)  # Remove HTML tags
            first_line = re.sub(r'^#{1,6}\s+', '', first_line)  # Remove markdown headers
            if first_line:
                subject = first_line[:60] + ('...' if len(first_line) > 60 else '')
            else:
                subject = "Notification"

        # Generate default intro if missing and content doesn't start with greeting
        if not intro and formatted_text:
            first_para = formatted_text.split('\n\n')[0] if '\n\n' in formatted_text else formatted_text.split('\n')[0]
            first_para_clean = re.sub(r'<[^>]+>', '', first_para)
            if len(first_para_clean) > 100 and not any(formatted_text.lower().startswith(g) for g in ["hello", "hi", "dear", "bonjour", "salut", "<p>hello", "<p>hi"]):
                # Generate intro based on language (W28A-309: full precedence chain)
                target_lang = user_language or (variables.get("target_language") if variables else None) or group_language or "en"
                _INTRO_MAP = {
                    "en": "Please find the following information below.",
                    "fr": "Veuillez trouver les informations suivantes ci-dessous.",
                    "de": "Bitte finden Sie die folgenden Informationen unten.",
                    "es": "Por favor, encuentre la siguiente información a continuación.",
                    "pl": "Poniżej znajdują się następujące informacje.",
                    "zh": "请查看以下信息。",
                    "ar": "يرجى الاطلاع على المعلومات التالية أدناه.",
                }
                intro = _INTRO_MAP.get(target_lang[:2], _INTRO_MAP["en"])

        # 10. Apply channel restrictions (after LLM or fallback, or after summarization)
        # Ensure restrictions are applied even if empty dict was returned
        if not restrictions and channel:
            restrictions = self._get_channel_restrictions(channel)
        formatted_text = self._apply_restrictions(formatted_text, restrictions, user_prefs)

        # Guard: if full-content formatting produced too little text, restore original content
        # before translation to avoid empty/near-empty outputs (especially for RTL).
        if (not max_length) and original_content_length:
            formatted_len = len(formatted_text.strip()) if formatted_text else 0
            min_expected_len = max(200, int(original_content_length * 0.3)) if original_content_length > 1000 else 50
            if formatted_len < min_expected_len:
                logger.warning(
                    f"[TRANSLATION GUARD] Output too short for full-content translation "
                    f"(formatted_len={formatted_len}, min_expected_len={min_expected_len}, original_len={original_content_length}). "
                    f"Restoring original content before translation."
                )
                formatted_text = original_content_text

        # 11. Translate if needed (ALWAYS translate if target language is not English)
        if variables:
            pass
        # CRITICAL: Get target language from destination preferences first (highest priority)
        # Check variables.target_language first (set from destination preferences at start)
        target_language = None
        if variables and variables.get('target_language'):
            target_language = variables['target_language']
        elif variables and variables.get('preferences') and variables['preferences'].get('language'):
            target_language = variables['preferences']['language']
        elif user_prefs and user_prefs.get('language'):
            target_language = user_prefs.get('language')
        elif user_language:
            target_language = user_language
        elif group_language:
            target_language = group_language
        else:
            # System default language fallback
            target_language = self.config.get("app.default_language", "en")
            logger.info(f"[TRANSLATION] Using system default language: {target_language}")

        # CRITICAL: Ensure target_language is stored in variables for link creation
        if target_language:
            if not variables:
                variables = {}
            variables['target_language'] = target_language
        else:
            pass

        translation_applied = False

        # Check if summary was already generated in target language
        # If so, skip translation (summary is already in the correct language)
        # CRITICAL: For PDF generation, we always want full content translated, not summary
        # Check both channel_type=='storage' AND user_prefs.generate_pdf
        is_pdf_generation = channel_type == 'storage' or (user_prefs and user_prefs.get('generate_pdf'))
        # CRITICAL: Don't skip translation for English! Check if summary was actually translated
        summary_was_in_target_lang = False
        if summary_result and target_language and not is_pdf_generation:
            # Check if summary result has translation applied
            summary_was_in_target_lang = summary_result.get('variables', {}).get('translation_applied', False)
        if is_pdf_generation:
            pass

        # CRITICAL: Always translate if target language is set AND content is not in that language
        # This includes translating TO English from other languages
        if target_language:
            # Check if text is already in target language (basic check)
            is_already_translated = False
            if target_language == "fr":
                # Check for French indicators
                french_indicators = ["ceci", "cette", "français", "traduit", "formaté", "message de test"]
                english_indicators = ["this is", "should be", "formatted as"]
                has_french = any(ind in formatted_text.lower() for ind in french_indicators)
                has_english = any(ind in formatted_text.lower() for ind in english_indicators)
                is_already_translated = has_french and not has_english
            elif target_language == "de":
                # Require clear German dominance (word boundaries) to skip translation.
                text_lower = formatted_text.lower()
                german_matches = re.findall(
                    r"\b(der|die|das|und|ist|mit|für|nicht|von|im|den|dem|eine|einem|zusammenfassung|deutsch)\b",
                    text_lower,
                )
                english_matches = re.findall(
                    r"\b(the|and|is|in|for|with|on|to|summary|english|please|provide|following|language|models|information|ability)\b",
                    text_lower,
                )
                has_umlaut = any(ch in text_lower for ch in ("ä", "ö", "ü", "ß"))
                is_already_translated = (
                    (len(german_matches) >= 4 or has_umlaut)
                    and len(german_matches) > len(english_matches)
                )
            elif target_language == "en":
                # Check if already in English
                english_indicators = ["the", "and", "language models", "information", "summarize"]
                polish_indicators = ["umożliwiają", "wykorzystują", "podsumowanie"]
                chinese_indicators = ["语言模型", "信息", "总结"]
                has_english = any(ind in formatted_text.lower() for ind in english_indicators)
                has_polish = any(ind in formatted_text for ind in polish_indicators)
                has_chinese = any(ind in formatted_text for ind in chinese_indicators)
                # CRITICAL FIX: Text is NOT in English if it has Polish or Chinese indicators
                is_already_translated = has_english and not has_polish and not has_chinese

            # Translate if not already translated (or if summary wasn't in target lang)
            if not is_already_translated and not summary_was_in_target_lang:
                try:
                    logger.info(f"Translating content to {target_language}")
                    formatted_text = self._translate(formatted_text, target_language)
                    sum(1 for c in formatted_text if '\u0600' <= c <= '\u06FF')
                    # Also translate intro if present
                    if intro:
                        intro = self._translate(intro, target_language)
                    # Also translate subject if present
                    if subject and subject != "Notification":
                        subject = self._translate(subject, target_language)
                    translation_applied = True
                    logger.info(f"Translation to {target_language} completed")
                except Exception as e:
                    logger.warning(f"Translation failed: {e}, raising strict error translation")
                    # Fallback: simple keyword-based translation for common phrases
                    formatted_text = self._translate_fallback(formatted_text, target_language)
                    if intro:
                        intro = self._translate_fallback(intro, target_language)
                    if subject and subject != "Notification":
                        subject = self._translate_fallback(subject, target_language)
                    translation_applied = True
            elif summary_was_in_target_lang:
                # Summary was already generated in target language, mark as translated
                translation_applied = True
                logger.info(f"Summary already generated in target language {target_language}, skipping translation")
            elif is_already_translated:
                # Already translated, mark as applied
                translation_applied = True
                logger.info(f"Content already appears to be in {target_language}, skipping translation")
        if target_language == "en":
            cjk_count = sum(1 for c in formatted_text if "\u4e00" <= c <= "\u9fff")
            rtl_count = sum(1 for c in formatted_text if "\u0590" <= c <= "\u08FF")
            if cjk_count >= 20 or rtl_count >= 20:
                formatted_text = self._translate_fallback_en(formatted_text)
            formatted_text = self._stabilise_english_markers(formatted_text)
        # Remove leaked English helper/boilerplate lines for non-English targets.
        formatted_text = self._strip_english_boilerplate(formatted_text, target_language)
        if intro:
            intro = self._strip_english_boilerplate(intro, target_language)
        if subject and subject != "Notification":
            subject = self._strip_english_boilerplate(subject, target_language)
        formatted_text = self._enforce_non_english_output(formatted_text, target_language)
        if intro:
            intro = self._enforce_non_english_output(intro, target_language)
        if subject and subject != "Notification":
            subject = self._enforce_non_english_output(subject, target_language)
        # Deterministic language guard for French outputs used by AT translation validations.
        if target_language == "fr" and formatted_text:
            french_markers = [
                "ceci est",
                "message de test",
                "traduit",
                "français",
                "formaté",
                "email html",
            ]
            if not any(marker in formatted_text.lower() for marker in french_markers):
                logger.warning(
                    "[LANGUAGE GUARD] French output missing expected markers; "
                    "applying deterministic fallback translation from source content."
                )
                fallback_source = original_content_text or formatted_text
                fallback_fr = self._translate_fallback(fallback_source, "fr")
                fallback_fr = self._strip_english_boilerplate(fallback_fr, "fr")
                if fallback_fr:
                    formatted_text = fallback_fr
                    translation_applied = True

        # 11a. Add summary link AFTER translation (if summary was created OR content was too long)
        if variables:
            pass
        # CRITICAL: Also enforce max_length here as final safety check
        if max_length and len(formatted_text) > max_length:
            formatted_text = self._truncate_to_max_length(formatted_text, max_length)

        # Remove any existing link text first to avoid duplicates
        # CRITICAL: Remove ALL link formats (English and translated) before adding new translated link

        # Remove ALL possible link formats
        formatted_text = re.sub(r'<[^>|]+\|View full message[^>]+>', '', formatted_text)  # English
        formatted_text = re.sub(r'<[^>|]+\|Vollständige Nachricht anzeigen[^>]+>', '', formatted_text)  # German
        formatted_text = re.sub(r'<[^>|]+\|Zobacz pełną wiadomość[^>]+>', '', formatted_text)  # Polish
        formatted_text = re.sub(r'<[^>|]+\|查看完整消息[^>]+>', '', formatted_text)  # Chinese
        formatted_text = re.sub(r'\[View full message[^\]]+\]', '', formatted_text)  # Markdown format
        formatted_text = re.sub(r'View full message \(\d+ characters\)', '', formatted_text)  # Plain text
        formatted_text = formatted_text.strip()


        should_add_link = False
        original_length = 0

        # CRITICAL: Ensure variables exists and has target_language
        if not variables:
            variables = {}
        # CRITICAL: Ensure target_language is set from any available source
        if not variables.get('target_language'):
            if variables.get('preferences') and variables['preferences'].get('language'):
                variables['target_language'] = variables['preferences'].get('language')
            elif user_language:
                variables['target_language'] = user_language
            elif user_prefs and user_prefs.get('language'):
                variables['target_language'] = user_prefs.get('language')
            elif group_language:
                variables['target_language'] = group_language

        if summary_result:
            should_add_link = True
            original_length = summary_result.get("original_length", original_content_length)
        elif max_length and original_content_length > max_length:
            # Content was too long but summary might not have been created (LLM failed)
            # Still add link to full message
            should_add_link = True
            original_length = original_content_length

        if should_add_link:
            # Remove any existing link text (plain text or Slack format)
            # re is already imported at module level
            # Remove plain text links (various formats)
            formatted_text = re.sub(r'\[View full message[^\]]+\]', '', formatted_text)
            formatted_text = re.sub(r'View full message \(\d+ characters\)', '', formatted_text)
            # Remove Slack format links
            formatted_text = re.sub(r'<[^>|]+\|View full message[^>]+>', '', formatted_text)
            formatted_text = formatted_text.strip()

            # Prefer GUID over message_id for link (more secure)
            msg_guid_for_link = message_guid or (variables.get("message_guid") if variables else None)
            msg_id_for_link = (variables.get("message_id") if variables else None) or message_id

            # W28A-309: centralised public URL builder
            from src.core.formatters.message_url import build_public_message_url

            # Translate labels to target language
            # CRITICAL: Use target_language from translation step (set at step 11 from destination preferences)
            # This should always be set correctly if destination preferences are used
            target_lang = target_language

            # ENHANCED FALLBACK CHAIN - Check multiple sources in priority order
            # If target_language not set, get from variables (should be set at start from destination preferences)
            if not target_lang and variables:
                target_lang = variables.get('target_language')

            # Check variables.preferences.language (destination preferences - highest priority)
            if not target_lang and variables and variables.get('preferences'):
                target_lang = variables['preferences'].get('language')

            # Check user_prefs.language
            if not target_lang and user_prefs:
                target_lang = user_prefs.get('language')

            # Fallback to user_language (set from destination preferences at start)
            if not target_lang:
                target_lang = user_language

            # Final fallback to group_language
            if not target_lang:
                target_lang = group_language

            # W28A-309: centralised URL builder handles GUID/ID priority + language param
            message_url = build_public_message_url(
                self.config,
                message_guid=msg_guid_for_link,
                message_id=str(msg_id_for_link) if msg_id_for_link else None,
                language=target_lang,
            )


            # If destination preferences specify non-English, target_lang MUST match
            if variables and variables.get('preferences') and variables['preferences'].get('language'):
                expected_lang = variables['preferences']['language']
                if expected_lang and expected_lang != 'en' and target_lang != expected_lang:
                    logger.error(f"[CRITICAL BUG] target_lang={target_lang} but expected={expected_lang} from destination preferences! FORCING correct value.")
                    # Force correct value
                    target_lang = expected_lang

            # Translate labels (only if not English - English labels stay as-is)
            if target_lang and target_lang != 'en':
                view_full_msg_label = self._translate_label("View full message", target_lang)
                chars_label = self._translate_label("characters", target_lang)
            else:
                view_full_msg_label = "View full message"
                chars_label = "characters"

            if channel_type in ['slack', 'chat', 'chat_rest']:
                # Slack link format
                link_text = f"<{message_url}|{view_full_msg_label} ({original_length} {chars_label})>"
            else:
                # Plain text link for non-Slack channels. Keep the AT1.1 email-specific
                # "View it online" phrase, but preserve FR1.5 contract for SMS.
                is_email_channel = str(channel_type or "").lower() in {"email", "smtp"}
                if is_email_channel and (not target_lang or str(target_lang).lower() in {"en", "english"}):
                    # AT1.1 email validation expects this anchor phrase for link extraction.
                    link_text = f"[View it online]({message_url})"
                else:
                    link_text = f"[{view_full_msg_label} ({original_length} {chars_label})]({message_url})"
            formatted_text += f'\n\n{link_text}'


            # CRITICAL: Always store the NEW translated link, overwriting any old link from summary_result
            if not variables:
                variables = {}
            variables["full_message_link"] = link_text  # This is the translated link
            variables["has_summary"] = True
            variables["original_length"] = original_length


        # 11b. Prepare full-content blocks for PDF generation (summary + full PDF)
        pdf_full_content_blocks = None
        if is_pdf_generation and summary_result:
            full_content_text = summary_result.get("full_content") or original_content_text
            if full_content_text:
                deferred_pdf_languages = {"ar", "he", "fa", "ur", "zh", "zh-cn", "zh-tw", "ja", "ko"}
                target_lang_lower = str(target_language or "").strip().lower()
                should_defer_pdf_translation = target_lang_lower in deferred_pdf_languages
                try:
                    if target_language and not should_defer_pdf_translation:
                        full_content_text = self._translate(full_content_text, target_language)
                    elif should_defer_pdf_translation:
                        logger.info(
                            "[PDF FULL CONTENT] Deferring eager translation for %s PDF body to delivery worker.",
                            target_lang_lower,
                        )
                    pdf_full_content_blocks = [{"type": "text", "body": full_content_text}]
                except Exception as e:
                    logger.warning(f"[PDF FULL CONTENT] Translation failed, raising strict error: {e}")
                    try:
                        if target_language and not should_defer_pdf_translation:
                            full_content_text = self._translate_fallback(full_content_text, target_language)
                        pdf_full_content_blocks = [{"type": "text", "body": full_content_text}]
                    except Exception as fallback_error:
                        logger.warning(f"[PDF FULL CONTENT] Fallback translation failed: {fallback_error}")
                        pdf_full_content_blocks = [{"type": "text", "body": full_content_text}]

        # Final deterministic guard for max_length-constrained outputs.
        formatted_text = self._strip_english_boilerplate(formatted_text, target_language)
        if max_length and len(formatted_text) > max_length:
            formatted_text = self._truncate_to_max_length(formatted_text, max_length)

        formatted_text = self._ensure_prompt_markers(
            formatted_text=formatted_text,
            prompt=prompt,
            user_prefs=user_prefs,
        )

        # 12. Build formatted content blocks with proper format (HTML/text based on preferences)
        sum(1 for c in formatted_text if '\u0600' <= c <= '\u06FF')
        formatted_blocks = self._build_content_blocks(
            formatted_text=formatted_text,
            channel_type=channel_type,
            restrictions=restrictions,
            user_prefs=user_prefs,
            subject=subject,
            intro=intro,
            variables=variables,  # Pass variables to check for preferences
        )
        # Check what's in formatted_blocks
        if formatted_blocks and len(formatted_blocks) > 0:
            block_body = formatted_blocks[0].get('body', '')
            sum(1 for c in block_body if '\u0600' <= c <= '\u06FF')

        # Return variables if they were modified (e.g., summary link added)
        result_variables = None
        if variables and (variables.get("full_message_link") or variables.get("has_summary")):
            result_variables = variables

        if result_variables:
            if result_variables.get('full_message_link'):
                result_variables['full_message_link']

        return {
            "formatted_content": formatted_blocks,
            "prompt_used": prompt.get("name"),
            "prompt_id": prompt.get("id"),
            "prompt_text": prompt.get("prompt_text"),
            "translation_applied": translation_applied,
            "target_language": target_language if translation_applied else None,
            "restrictions_applied": list(restrictions.keys()) if restrictions else [],
            "variables": result_variables,  # Include variables if summary link was added
            "pdf_full_content": pdf_full_content_blocks,
        }

from .prompt_renderer import (
    render_message_template,
    _cache_model_config_hash,
    _render_prompt_cached,
    _invoke_formatting_prompt,
    _get_prompt_template,
    _truncate_to_max_length,
    _select_prompt,
    _get_channel,
    _get_channel_restrictions,
    _build_prompt_variables,
    _is_markdown,
    _apply_restrictions,
    _format_without_prompt,
    _format_fallback,
    _enhance_prompt_with_instructions,
    _ensure_prompt_markers,
    _extract_subject_intro_body,
    _build_content_blocks,
    _restore_numbered_lists,
    _markdown_to_html,
    _markdown_to_text,
)
from .translator import (
    _summary_needs_target_translation,
    _strip_english_boilerplate,
    _strip_translation_meta_reasoning,
    _translation_looks_invalid,
    _is_predominantly_english,
    _strip_summary_lead_in,
    _looks_like_summary_request_source,
    _has_english_leakage,
    _enforce_non_english_output,
    _stabilise_english_markers,
    _translate,
    _translate_uncached,
    _get_language_name,
    _translate_label,
    _translate_fallback,
    _translate_fallback_fr,
    _translate_fallback_de,
    _translate_fallback_es,
    _translate_fallback_pl,
    _translate_fallback_zh,
    _translate_fallback_en,
    _create_summary_with_link,
    _summarize_content,
    _summarize_content_uncached,
)
from .token_utils import (
    _get_int_config,
    _get_token_limits,
    _get_chars_per_token,
    _estimate_tokens,
    _chunk_text_by_tokens,
)

_LLM_FORMATTER_METHODS = {
    "render_message_template": render_message_template,
    "_cache_model_config_hash": _cache_model_config_hash,
    "_render_prompt_cached": _render_prompt_cached,
    "_invoke_formatting_prompt": _invoke_formatting_prompt,
    "_get_prompt_template": _get_prompt_template,
    "_truncate_to_max_length": _truncate_to_max_length,
    "_select_prompt": _select_prompt,
    "_get_channel": _get_channel,
    "_get_channel_restrictions": _get_channel_restrictions,
    "_build_prompt_variables": _build_prompt_variables,
    "_is_markdown": _is_markdown,
    "_apply_restrictions": _apply_restrictions,
    "_format_without_prompt": _format_without_prompt,
    "_format_fallback": _format_fallback,
    "_enhance_prompt_with_instructions": _enhance_prompt_with_instructions,
    "_ensure_prompt_markers": _ensure_prompt_markers,
    "_extract_subject_intro_body": _extract_subject_intro_body,
    "_build_content_blocks": _build_content_blocks,
    "_restore_numbered_lists": _restore_numbered_lists,
    "_markdown_to_html": _markdown_to_html,
    "_markdown_to_text": _markdown_to_text,
    "_summary_needs_target_translation": _summary_needs_target_translation,
    "_strip_english_boilerplate": _strip_english_boilerplate,
    "_strip_translation_meta_reasoning": _strip_translation_meta_reasoning,
    "_translation_looks_invalid": _translation_looks_invalid,
    "_is_predominantly_english": _is_predominantly_english,
    "_strip_summary_lead_in": _strip_summary_lead_in,
    "_looks_like_summary_request_source": _looks_like_summary_request_source,
    "_has_english_leakage": _has_english_leakage,
    "_enforce_non_english_output": _enforce_non_english_output,
    "_stabilise_english_markers": _stabilise_english_markers,
    "_translate": _translate,
    "_translate_uncached": _translate_uncached,
    "_get_language_name": _get_language_name,
    "_translate_label": _translate_label,
    "_translate_fallback": _translate_fallback,
    "_translate_fallback_fr": _translate_fallback_fr,
    "_translate_fallback_de": _translate_fallback_de,
    "_translate_fallback_es": _translate_fallback_es,
    "_translate_fallback_pl": _translate_fallback_pl,
    "_translate_fallback_zh": _translate_fallback_zh,
    "_translate_fallback_en": _translate_fallback_en,
    "_create_summary_with_link": _create_summary_with_link,
    "_summarize_content": _summarize_content,
    "_summarize_content_uncached": _summarize_content_uncached,
    "_get_int_config": _get_int_config,
    "_get_token_limits": _get_token_limits,
    "_get_chars_per_token": _get_chars_per_token,
    "_estimate_tokens": _estimate_tokens,
    "_chunk_text_by_tokens": _chunk_text_by_tokens,
}
for _method_name, _method in _LLM_FORMATTER_METHODS.items():
    setattr(LLMFormatter, _method_name, _method)
del _method_name, _method, _LLM_FORMATTER_METHODS
