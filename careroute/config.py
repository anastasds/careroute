"""Configuration and secure secret management for CareRoute.

Loads settings from environment variables with automatic fallback to Google Cloud
Secret Manager when running in GCP environments, strictly adhering to the zero-hardcoded-secrets
rule.
"""

from __future__ import annotations

import os
from typing import Optional


class CareRouteConfig:
    """CareRoute configuration provider with secure Secret Manager resolution."""

    def __init__(self) -> None:
        self.env: str = os.getenv("CAREROUTE_ENV", "development")
        self.gcp_project_id: str = os.getenv("GCP_PROJECT_ID")
        self.gcp_secret_name: str = os.getenv("GCP_SECRET_NAME", "careroute-gemini-api-key")
        self.storage_backend: str = os.getenv("CAREROUTE_STORAGE_BACKEND", "agentplatform")
        self.firestore_db: str = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
        self.pro_model_name: str = os.getenv("CAREROUTE_PRO_MODEL", "gemini-2.5-pro")
        self.flash_model_name: str = os.getenv("CAREROUTE_FLASH_MODEL", "gemini-2.5-flash")
        self.otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "careroute-agent")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.enable_dlp: bool = os.getenv("CAREROUTE_ENABLE_DLP", "false").lower() in ("true", "1", "yes")
        self._api_key: Optional[str] = None

    @property
    def gemini_api_key(self) -> str:
        """Retrieves the Gemini API Key securely.
        
        Attempts local environment variable injection first, then queries GCP Secret
        Manager if running in GCP and the key is not present locally.
        """
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key and env_key != "your-gemini-api-key-here":
            return env_key

        if self._api_key:
            return self._api_key

        # Try Google Cloud Secret Manager if in GCP production
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("K_SERVICE"):
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                name = f"projects/{self.gcp_project_id}/secrets/{self.gcp_secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                self._api_key = response.payload.data.decode("UTF-8").strip()
                return self._api_key
            except Exception:
                pass

        # Return placeholder for mock/offline testing
        return os.getenv("GEMINI_API_KEY", "mock-gemini-key")


# Singleton instance
settings = CareRouteConfig()
