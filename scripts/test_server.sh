#!/bin/bash
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

# Quick test script to verify API server functionality

: "${API_URL:?Set API_URL to your API base URL}"
: "${API_KEY:?Set API_KEY to your API key}"

echo "=== Notification Agent API Server Test ==="
echo ""

# Test 1: Root endpoint
echo "Test 1: GET / (root)"
curl -s $API_URL/ | python3 -m json.tool
echo ""

# Test 2: Health check
echo "Test 2: GET /health"
curl -s $API_URL/health | python3 -m json.tool
echo ""

# Test 3: Status (requires auth)
echo "Test 3: GET /status (authenticated)"
curl -s -H "X-API-Key: $API_KEY" $API_URL/status | python3 -m json.tool
echo ""

# Test 4: List channels
echo "Test 4: GET /channels (authenticated)"
curl -s -H "X-API-Key: $API_KEY" $API_URL/channels | python3 -m json.tool
echo ""

# Test 5: Create message
echo "Test 5: POST /messages (create notification)"
curl -s -X POST \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "destinations": [
      {"channel": "<DEFAULT_CHANNEL_NAME>", "address": "test@example.com"}
    ],
    "content": [
      {"type": "text", "body": "Test notification from script"}
    ]
  }' \
  $API_URL/messages | python3 -m json.tool
echo ""

echo "=== Tests Complete ==="
