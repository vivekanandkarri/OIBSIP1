"""Base handler module for PyVoice Assistant.

Defines the BaseHandler interface and provides shared utility methods,
such as secure HTTPS networking with retry logic.
"""

import logging
import time
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger("PyVoice.Handlers.Base")


class HandlerError(Exception):
    """Exception raised by handlers when executing tasks."""
    pass


class BaseHandler:
    """Base class that all task handlers inherit from."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the base handler.

        Args:
            config: User configuration and preferences loaded from config.yaml.
        """
        self.config = config

    def execute(self, entities: Dict[str, Any]) -> str:
        """Executes the handler logic with extracted entities.

        Args:
            entities: Dictionary of entities extracted by the NLP engine.

        Returns:
            A string response that the assistant should speak.

        Raises:
            HandlerError: If the task execution fails.
        """
        raise NotImplementedError("Subclasses must implement the execute method.")

    def secure_request(self, 
                       url: str, 
                       method: str = "GET", 
                       headers: Optional[Dict[str, str]] = None, 
                       json_data: Optional[Dict[str, Any]] = None,
                       params: Optional[Dict[str, Any]] = None,
                       retries: int = 1) -> requests.Response:
        """Performs a secure HTTPS request with automatic single retry.

        Args:
            url: The request URL (must use HTTPS).
            method: HTTP method.
            headers: Headers dictionary.
            json_data: JSON payload.
            params: Query parameters.
            retries: Number of retry attempts.

        Returns:
            The requests.Response object.

        Raises:
            HandlerError: If network request fails or URL is insecure.
        """
        # Privacy & Security: Enforce HTTPS-only
        if not url.lower().startswith("https://") and not url.lower().startswith("http://localhost") and not url.lower().startswith("http://127.0.0.1"):
            raise HandlerError(f"Insecure connection blocked. URLs must use HTTPS: {url}")

        attempt = 0
        while attempt <= retries:
            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=params,
                    timeout=5.0
                )
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                attempt += 1
                logger.warning(f"Request failed (attempt {attempt}/{retries + 1}): {e}")
                if attempt > retries:
                    raise HandlerError(f"Network error: Could not reach service. Details: {e}")
                time.sleep(1.0)
        
        raise HandlerError("Network error: Unexpected termination of request loop.")
