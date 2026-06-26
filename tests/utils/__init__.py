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

"""Test utilities for notification agent tests"""

from .test_message_loader import (
    load_test_message,
    get_test_message_path,
    list_available_messages,
    TEST_MESSAGES,
)

from .pdf_validator import (
    PDFValidator,
    validate_pdf_file,
    validate_pdf_bytes,
)

from .content_validator import (
    extract_images_from_html,
    extract_links_from_html,
    validate_html_has_images,
    validate_html_has_links,
    extract_text_from_html,
    validate_text_content,
    validate_api_response_has_images,
)

__all__ = [
    "load_test_message",
    "get_test_message_path",
    "list_available_messages",
    "TEST_MESSAGES",
    "PDFValidator",
    "validate_pdf_file",
    "validate_pdf_bytes",
    "extract_images_from_html",
    "extract_links_from_html",
    "validate_html_has_images",
    "validate_html_has_links",
    "extract_text_from_html",
    "validate_text_content",
    "validate_api_response_has_images",
]
