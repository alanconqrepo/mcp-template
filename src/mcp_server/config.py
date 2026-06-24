from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    LOG_LEVEL: str = "info"

    # MCP
    MCP_SERVER_NAME: str = "mcp-server-template"
    MCP_MOUNT_PATH: str = "/mcp"

    # Auth
    AUTH_MODE: Literal["api_key", "oauth2", "none"] = "api_key"
    API_KEYS: list[str] = []

    # OAuth2
    OAUTH2_TOKEN_URL: str | None = None
    OAUTH2_JWKS_URL: str | None = None
    OAUTH2_AUDIENCE: str | None = None
    OAUTH2_ISSUER: str | None = None

    # CORS
    CORS_ORIGINS: list[str] = []

    # Langfuse
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_HOST: str | None = None

    # Wiki.js
    WIKIJS_URL: str | None = None
    WIKIJS_API_TOKEN: str | None = None

    # SQL Server — named connections stored as JSON dict
    # Example: {"default": {"host": "...", "database": "...", "username": "...", "password": "..."}}
    SQL_CONNECTIONS: dict[str, dict] = {}
    SQL_DEFAULT_CONNECTION: str = "default"

    # Azure Blob Storage — metadata .md files per table/view
    AZURE_BLOB_CONNECTION_STRING: str = ""
    AZURE_BLOB_CONTAINER_NAME: str = ""
    AZURE_BLOB_METADATA_PREFIX: str = ""  # e.g. "metadata/" — prepended to schema/object.md

    # Baserow
    BASEROW_URL: str = "http://baserow"
    BASEROW_TOKEN: str = ""

    # Prefect
    PREFECT_URL: str = "http://prefect-server:4200/api"
    PREFECT_API_KEY: str | None = None  # optional — for Prefect Cloud or secured self-hosted

    # DeepL
    DEEPL_API_KEY: str = ""
    DEEPL_BLOB_CONTAINER: str = ""
    DEEPL_BLOB_OUTPUT_PREFIX: str = "deepl/translated/"

    # Microsoft Graph / Outlook (Auth Code PKCE, multi-user)
    AZURE_TENANT_ID: str | None = None
    AZURE_CLIENT_ID: str | None = None
    OUTLOOK_REDIRECT_URI: str = "http://localhost:8000/auth/outlook/callback"
    OUTLOOK_TOKENS_DIR: str = ".outlook_tokens"

    # DocuWare (shared service account)
    DOCUWARE_URL: str = ""           # e.g. https://docuware.mycompany.com
    DOCUWARE_USERNAME: str = ""
    DOCUWARE_PASSWORD: str = ""
    DOCUWARE_ORGANIZATION: str = ""  # DocuWare organization name
    DOCUWARE_BLOB_PREFIX: str = "docuware/"  # blob prefix for downloaded files

    # Azure DevOps
    AZURE_DEVOPS_ORG_URL: str = "https://dev.azure.com/myorg"
    AZURE_DEVOPS_DEFAULT_PROJECT: str = ""
    AZURE_DEVOPS_DEFAULT_PAT: str | None = None

    @model_validator(mode="after")
    def validate_oauth2_config(self) -> "Settings":
        if self.AUTH_MODE == "oauth2" and not self.OAUTH2_JWKS_URL:
            raise ValueError("OAUTH2_JWKS_URL is required when AUTH_MODE=oauth2")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
