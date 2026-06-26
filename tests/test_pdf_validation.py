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
Quick PDF validation test - checks if PDF is properly formatted
"""
import json
import re
import subprocess
import sys
from urllib.parse import urlparse

from src.config import get_config


def main() -> int:
    config = get_config()
    db_uri = config.get("db.uri")
    storage_base_url = config.get("storage.local.base_url") or config.get("storage.base_url")
    if not db_uri:
        raise RuntimeError("Missing required configuration: db.uri")
    if not storage_base_url:
        raise RuntimeError("Missing required configuration: storage.local.base_url/storage.base_url")

    parsed = urlparse(db_uri)
    if parsed.scheme != "sqlite3":
        raise RuntimeError("test_pdf_validation requires sqlite3 db.uri")
    db_path = parsed.path

    result = subprocess.run(
        [
            "sqlite3",
            db_path,
            "SELECT personalised_payload FROM deliveries WHERE id = (SELECT MAX(id) FROM deliveries);",
        ],
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    text = payload.get("text", "")
    pdf_match = re.search(r"(http[^ ]+\.pdf)", text, re.IGNORECASE)

    if not pdf_match:
        print("No PDF URL found")
        print(f"Message text: {text}")
        return 1

    pdf_url = pdf_match.group(1)
    if not pdf_url.startswith(storage_base_url.rstrip("/") + "/"):
        print("PDF URL does not match configured storage base URL")
        print(f"Storage base URL: {storage_base_url}")
        return 1
    pdf_file = pdf_url.replace(storage_base_url.rstrip("/") + "/", "")
    print(f"PDF URL: {pdf_url}")
    print(f"PDF File: {pdf_file}")

    print(f"Testing PDF: {pdf_file}")
    print("=" * 80)

    result = subprocess.run(
        ["pdftotext", pdf_file, "-"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Failed to extract PDF text")
        return 1

    pdf_text = result.stdout

    print("PDF Text (first 500 chars):")
    print(pdf_text[:500])
    print("\n" + "=" * 80)

    separator = "------------------------------------------------------------"
    if separator in pdf_text:
        print("FAILURE: PDF contains RAW MARKDOWN separator lines (----)")
        print("   This proves markdown was NOT converted to HTML")
        return 1
    print("PASS: No markdown separator lines")

    markdown_markers = ["**", "##", "###", "```"]
    found_markers = [marker for marker in markdown_markers if marker in pdf_text]
    if found_markers:
        print(f"FAILURE: PDF contains RAW MARKDOWN markers: {found_markers}")
        return 1
    print("PASS: No markdown markers")

    polish_words = ["wielkie", "modele", "językowe", "podsumowanie"]
    has_polish = sum(1 for word in polish_words if word.lower() in pdf_text.lower())

    if has_polish < 3:
        print(f"FAILURE: PDF not in Polish (only {has_polish} Polish words found)")
        return 1
    print("PASS: PDF is in Polish")

    print("\n" + "=" * 80)
    print("ALL PDF VALIDATIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
