// Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

window.__RUNTIME_CONFIG__ = {
  ENV: 'dev',
  API_BASE_URL: 'http://127.0.0.1:8021',
  MCP_BASE_URL: 'http://127.0.0.1:8022',
  A2A_BASE_URL: 'http://127.0.0.1:8023',
  AUTH_MODE: 'cookie',
  OIDC_ISSUER: 'https://issuer.example.com',
  OIDC_CLIENT_ID: 'cloud-dog-notification-agent',
  OIDC_REDIRECT_URI: 'http://localhost:5178/login',
  OIDC_SCOPE: 'openid profile email',
  APP_VERSION: '',
  PRODUCT_NAME: 'Cloud-Dog Notification agent',
  PRODUCT_DESCRIPTION: 'Multi-channel notification platform composed of four servers (API/REST, MCP, A2A, Web UI/Admin); accepts requests to notify users across email, SMS, WhatsApp, and chat with LLM-formatted content.'
};
