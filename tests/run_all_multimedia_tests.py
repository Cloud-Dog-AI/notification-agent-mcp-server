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
Comprehensive Test Runner for All Multimedia Use Cases

Runs all tests that validate:
- UC1.6: Group Notification with Multimedia and Multi-Language PDFs (Enhanced with Slack)
- UC1.7: Personalized Multimedia Notifications with HTML Pages (Enhanced with Slack)
- UC1.8: Storage/Output Channel with Multi-Format and Multi-Language Support
- UC1.9: Multi-Channel Multimedia Delivery with All Formats

All tests validate:
- PDF generation with embedded images
- HTML pages with embedded images
- Slack delivery with summaries and links
- Email delivery with attachments and links
- All formats (MD, PDF, HTML, TXT)
- All languages (EN, FR, DE, PL)
- Image embedding
- Video links/references
"""

import subprocess
import sys
import os
from pathlib import Path

# Test files to run (using pytest file paths)
TEST_FILES = [
    # UC1.6: Multimedia PDF with Multi-Language (Enhanced)
    "tests/application/AT1.23_MultimediaPDF/test_multimedia_pdf.py",
    
    # UC1.6: Comprehensive PDF validation
    "tests/application/AT1.23_MultimediaPDF/test_pdf_image_embedding_validation.py",
    
    # UC1.6: Comprehensive multimedia validation
    "tests/application/AT1.23_MultimediaPDF/test_comprehensive_multimedia_validation.py",
    
    # UC1.7: Personalized HTML Pages (Original)
    "tests/application/AT1.24_HTMLPageMultimedia/test_uc1_7_end_to_end.py",
    
    # UC1.7: Personalized HTML Pages with Slack (Enhanced)
    "tests/application/AT1.24_HTMLPageMultimedia/test_uc1_7_with_slack.py",
    
    # UC1.8: Storage/Output Channel
    "tests/application/AT1.25_StorageOutputChannel/test_storage_output_all_formats_languages.py",
    
    # UC1.9: Multi-Channel Multimedia
    "tests/application/AT1.26_MultiChannelMultimedia/test_multichannel_all_formats.py",
]

def run_tests():
    """Run all multimedia tests"""
    print("="*80)
    print("COMPREHENSIVE MULTIMEDIA USE CASE TEST RUNNER")
    print("="*80)
    print()
    
    # Get project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Run each test
    results = []
    for test_file in TEST_FILES:
        print(f"\n{'='*80}")
        print(f"Running: {test_file}")
        print(f"{'='*80}\n")
        
        try:
            result = subprocess.run(
                ["python3", "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per test
            )
            
            results.append({
                "test": test_file,
                "passed": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            })
            
            if result.returncode == 0:
                print(f"✅ PASSED: {test_file}")
            else:
                print(f"❌ FAILED: {test_file}")
                print(result.stdout)
                print(result.stderr)
        
        except subprocess.TimeoutExpired:
            results.append({
                "test": test_file,
                "passed": False,
                "output": "",
                "error": "Test timed out after 5 minutes"
            })
            print(f"⏱️  TIMEOUT: {test_file}")
        
        except Exception as e:
            results.append({
                "test": test_file,
                "passed": False,
                "output": "",
                "error": str(e)
            })
            print(f"❌ ERROR: {test_file} - {e}")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    print("\nDetailed Results:")
    for result in results:
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        print(f"  {status}: {result['test']}")
        if not result["passed"] and result["error"]:
            print(f"    Error: {result['error'][:200]}")
    
    # Return exit code
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(run_tests())

