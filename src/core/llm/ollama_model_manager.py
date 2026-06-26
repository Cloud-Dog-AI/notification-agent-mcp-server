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
Description: Ollama Model Manager - Checks and loads Ollama models before use

Related Requirements: FR1.10, FR1.11
Related Tasks: T8
Related Architecture: CC3.1

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import time
from httpx import Client as SharedSyncHTTPClient, TimeoutException
from typing import Any, Optional, List
from urllib.parse import urljoin

from src.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaModelManager:
    """Manages Ollama instance including model availability and loading"""
    
    def __init__(self, base_url: str, logger: Optional[Any] = None,
                 auto_pull: bool = None, verify_ssl: bool = False):
        """
        Initialize Ollama manager
        
        Args:
            base_url: Ollama API base URL
            logger: Logger instance
            auto_pull: Whether to auto-pull models
            verify_ssl: Whether to verify SSL certificates (default: False for self-signed certs)
        """
        self.base_url = base_url.rstrip('/')
        self.logger = logger or get_logger(__name__)
        self.verify_ssl = verify_ssl

        if auto_pull is None:
            raise RuntimeError("Missing required configuration: llm.auto_pull")
        self.auto_pull = auto_pull
        # Shared long-lived sync HTTP client (W28A-93b-R1, AGENT-LESSONS §2.3).
        # cloud_dog_api_kit currently exposes async helpers; this synchronous
        # manager keeps one sync client per manager instead of per call.
        self._http_client: Any = None

        self.logger.debug(f"OllamaModelManager initialized: base_url={self.base_url}, auto_pull={self.auto_pull}")

    def _get_http_client(self, timeout: float = 5.0) -> Any:
        """Return a shared long-lived sync HTTP client, creating on first use."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = SharedSyncHTTPClient(verify=self.verify_ssl, timeout=timeout)
        return self._http_client

    def close(self) -> None:
        """Close the shared HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            self._http_client.close()
            self._http_client = None
    
    def check_connection(self) -> bool:
        """
        Check if Ollama server is reachable
        
        Returns:
            True if server is accessible, False otherwise
        """
        try:
            self.logger.debug(f"Checking Ollama connection at {self.base_url}...")
            client = self._get_http_client(timeout=5.0)
            response = client.get(urljoin(self.base_url, '/api/tags'))
            response.raise_for_status()
            self.logger.info("Ollama server is reachable")
            return True
        except Exception as e:
            self.logger.error(f"❌ Ollama server not reachable: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """
        List all available models in Ollama
        
        Returns:
            List of model names
        """
        try:
            client = self._get_http_client(timeout=5.0)
            response = client.get(urljoin(self.base_url, '/api/tags'))
            response.raise_for_status()
            data = response.json()
            models = [model['name'] for model in data.get('models', [])]
            self.logger.info(f"Found {len(models)} models: {models}")
            return models
        except Exception as e:
            self.logger.error(f"Error listing models: {e}")
            return []
    
    def model_exists(self, model_name: str) -> bool:
        """
        Check if a specific model is available in Ollama
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if model is available, False otherwise
        """
        models = self.list_models()
        exists = model_name in models
        
        if exists:
            self.logger.info(f"✅ Model '{model_name}' is available")
        else:
            self.logger.warning(f"❌ Model '{model_name}' is NOT available")
            self.logger.info(f"   Available models: {models if models else 'None'}")
        
        return exists
    
    def pull_model(self, model_name: str, stream: bool = True, max_wait: int = 600) -> bool:
        """
        Download/pull a model from Ollama registry
        
        Args:
            model_name: Name of the model to pull
            stream: Whether to stream the output (for progress)
            max_wait: Maximum wait time in seconds
            
        Returns:
            True if pull was successful, False otherwise
        """
        try:
            self.logger.info(f"⏳ Pulling model '{model_name}'... (this may take several minutes)")
            
            # Make the pull request
            payload = {'name': model_name, 'stream': stream}
            
            start_time = time.time()
            
            client = self._get_http_client(timeout=max_wait)
            if stream:
                # Stream response for progress tracking
                url = urljoin(self.base_url, '/api/pull')
                with client.stream('POST', url, json=payload) as response:
                    response.raise_for_status()
                    last_status = None
                    for line in response.iter_lines():
                        if time.time() - start_time > max_wait:
                            self.logger.error(f"❌ Pull operation timed out after {max_wait}s")
                            return False

                        try:
                            import json
                            data = json.loads(line)
                            status = data.get('status', '')
                            if status and status != last_status:
                                self.logger.info(f"   {status}")
                                last_status = status

                            # Check if pull completed
                            if data.get('status') == 'success' or (not data.get('status') and 'completed_at' in data):
                                elapsed = time.time() - start_time
                                self.logger.info(f"✅ Model '{model_name}' pulled successfully in {elapsed:.1f}s")
                                return True
                        except json.JSONDecodeError:
                            continue
            else:
                # Non-streaming request
                url = urljoin(self.base_url, '/api/pull')
                response = client.post(url, json=payload, timeout=max_wait)
                response.raise_for_status()
                elapsed = time.time() - start_time
                self.logger.info(f"✅ Model '{model_name}' pulled successfully in {elapsed:.1f}s")
                return True
            
            # If we get here, pull may have completed but we didn't detect it
            # Verify by checking if model exists now
            if self.model_exists(model_name):
                elapsed = time.time() - start_time
                self.logger.info(f"✅ Model '{model_name}' appears to be available after pull ({elapsed:.1f}s)")
                return True
            
            self.logger.error(f"❌ Pull operation completed but model '{model_name}' is still not available")
            return False
            
        except TimeoutException:
            self.logger.error(f"❌ Pull operation timed out after {max_wait}s")
            return False
        except Exception as e:
            self.logger.error(f"❌ Error pulling model '{model_name}': {e}")
            return False
    
    def ensure_model_loaded(self, model_name: str, auto_pull: Optional[bool] = None, 
                           max_wait: int = 600) -> bool:
        """
        Ensure a model is loaded in Ollama, optionally pulling it if necessary
        
        This function checks if a model exists. It will only pull if:
        1. auto_pull parameter is explicitly True, OR
        2. self.auto_pull is True (from env var or constructor), OR
        3. auto_pull parameter overrides the default
        
        Args:
            model_name: Name of the model to ensure is loaded
            auto_pull: Whether to automatically pull the model if not found
                      (None = use default from __init__)
            max_wait: Maximum wait time in seconds for pull operation
        
        Returns:
            True if model is now available, False otherwise
        """
        self.logger.info(f"Ensuring model '{model_name}' is available...")
        
        # Check if server is reachable
        if not self.check_connection():
            self.logger.error("❌ Ollama server is not reachable")
            return False
        
        # Check if model exists
        if self.model_exists(model_name):
            return True
        
        # Model doesn't exist - determine if we should pull it
        should_pull = auto_pull if auto_pull is not None else self.auto_pull
        
        if not should_pull:
            self.logger.error(f"❌ Model '{model_name}' not available")
            self.logger.info(f"   To auto-pull, use: ensure_model_loaded('{model_name}', auto_pull=True)")
            self.logger.info("   Or set environment: OLLAMA_AUTO_PULL=true")
            return False
        
        # Try to pull the model
        self.logger.info(f"Attempting to pull model '{model_name}'...")
        return self.pull_model(model_name, stream=True, max_wait=max_wait)
