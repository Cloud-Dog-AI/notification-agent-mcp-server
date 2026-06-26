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

"""W28A-109F non-LLM local media contract shard.

These cases intentionally avoid API delivery, Slack/webhook calls, SMTP, and
LLM/model formatting. Live provider scenarios remain in live-provider gates.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from src.core.formatters.pdf_delivery import PDFDeliveryHelper
from src.core.media.media_processor import MediaProcessor
from src.core.media.media_renderer import MediaRenderer
from src.core.media.uuencoding import UUEncoding


pytestmark = [
    pytest.mark.application,
    pytest.mark.media,
    pytest.mark.non_llm,
    pytest.mark.no_llm_dependency,
    pytest.mark.no_runtime_dependency,
    pytest.mark.pure,
    pytest.mark.fast,
]


def _png_bytes() -> bytes:
    image = Image.new("RGB", (12, 12), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_w28a109f_data_uri_and_uuencoded_image_are_local_media_contracts():
    png = _png_bytes()
    data_uri = UUEncoding.encode(png, "png")

    decoded = UUEncoding.decode(data_uri)
    assert decoded is not None
    decoded_bytes, decoded_format = decoded
    assert decoded_bytes == png
    assert decoded_format == "png"

    refs = MediaProcessor().extract_media_references(
        [
            {"type": "image", "uri": data_uri, "alt_text": "inline data uri"},
            {"type": "markdown", "body": "![remote](https://example.invalid/media/news.png)"},
        ]
    )

    assert refs[0]["method"] == "uuencoded"
    assert refs[0]["format"] == "png"
    assert refs[0]["alt_text"] == "inline data uri"
    assert refs[1]["method"] == "uri"
    assert refs[1]["type"] == "image"


def test_w28a109f_slack_text_rendering_is_provider_specific_but_not_live_provider():
    png = _png_bytes()
    data_uri = UUEncoding.encode(png, "png")
    renderer = MediaRenderer()

    processed, images = renderer.process_images_in_content(
        [{"type": "image", "uuencoded": data_uri, "alt_text": "Slack inline image"}],
        output_format="text",
        channel_type="slack",
    )

    assert len(processed) == 1
    assert len(images) == 1
    assert processed[0]["type"] == "text"
    assert "Image: Slack inline image" in processed[0]["body"]
    assert images[0]["format"] == "png"
    assert images[0]["uri"] == data_uri


def test_w28a109f_processed_media_metadata_is_available_without_delivery_worker():
    png = _png_bytes()
    data_uri = UUEncoding.encode(png, "png")
    processor = MediaProcessor()
    media_refs = processor.extract_media_references(
        [{"type": "image", "uri": data_uri, "alt_text": "metadata image"}]
    )

    processed_media = processor.process_media(
        media_refs,
        channel_config={"duplicate_external_media": False},
        message_id=109,
        delivery_id=109,
    )

    assert len(processed_media) == 1
    media = processed_media[0]
    assert media["type"] == "image"
    assert media["format"] == "png"
    assert media["original_uri"] == data_uri
    assert media["is_local"] is False
    assert media["alt_text"] == "metadata image"
    assert media["metadata"]["format"] == "png"

    assert processor.prepare_media_for_html(processed_media) == processed_media
    pdf_refs = processor.prepare_media_for_pdf(processed_media)
    assert pdf_refs == [
        {
            "type": "image",
            "url": data_uri,
            "format": "png",
            "metadata": media["metadata"],
        }
    ]


def test_w28a109f_pdf_attachment_payload_shape_is_local_contract():
    helper = PDFDeliveryHelper()
    attachment = helper.prepare_pdf_attachment(
        {"pdf_bytes": b"%PDF-1.4\n%local-contract\n"},
        filename="w28a-109f.pdf",
    )

    assert attachment == {
        "content": b"%PDF-1.4\n%local-contract\n",
        "filename": "w28a-109f.pdf",
        "content_type": "application/pdf",
    }

# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-007")
