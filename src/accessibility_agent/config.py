"""
Configuration Management — loads settings from environment variables and
optional YAML/JSON config files.  All secrets must be supplied via
environment variables; never committed to version control.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserType(str, Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LLMProvider(str, Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    DISABLED = "disabled"  # Run in deterministic-only mode


class Settings(BaseSettings):
    """
    Central settings object.  All values can be overridden by environment
    variables prefixed with ``A11Y_`` (e.g. ``A11Y_BROWSER_TYPE=firefox``).
    """

    model_config = SettingsConfigDict(
        env_prefix="A11Y_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Browser ─────────────────────────────────────────────────────────────
    browser_type: BrowserType = BrowserType.CHROMIUM
    headless: bool = True
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)
    slow_mo: int = Field(default=0, ge=0, le=5000, description="ms delay between Playwright actions")
    browser_timeout: int = Field(default=30_000, ge=1_000, description="Default timeout ms")
    navigation_timeout: int = Field(default=60_000, ge=1_000, description="Navigation timeout ms")

    # ── Network ──────────────────────────────────────────────────────────────
    proxy_server: str | None = None
    extra_http_headers: dict[str, str] = Field(default_factory=dict)

    # ── Agent ────────────────────────────────────────────────────────────────
    max_agent_steps: int = Field(default=100, ge=1, le=500)
    max_interaction_elements: int = Field(default=50, ge=1)
    page_stabilization_ms: int = Field(default=1_500, ge=0)

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.DISABLED
    google_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=8_192, ge=256)

    # ── Axe-core ─────────────────────────────────────────────────────────────
    axe_version: str = "4.9.1"
    axe_tags: list[str] = Field(
        default=["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"],
        description="axe-core run configuration tags",
    )
    axe_timeout: int = Field(default=30_000, ge=1_000)

    # ── Evidence ─────────────────────────────────────────────────────────────
    evidence_dir: Path = Path("./evidence")
    screenshots_enabled: bool = True
    dom_snapshots_enabled: bool = True
    ax_tree_snapshots_enabled: bool = True

    # ── Reporting ─────────────────────────────────────────────────────────────
    report_dir: Path = Path("./reports")
    report_formats: list[str] = Field(default=["json", "html"])

    # ── Security / Redaction ─────────────────────────────────────────────────
    redact_patterns: list[str] = Field(
        default=[],
        description="Regex patterns to redact from logs/reports before LLM calls",
    )
    redact_headers: list[str] = Field(
        default=["authorization", "cookie", "x-api-key", "x-auth-token"],
        description="HTTP headers to strip before logging or sending to LLM",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: LogLevel = LogLevel.INFO
    log_json: bool = False  # Structured JSON logs for production

    # ── Deduplication ─────────────────────────────────────────────────────────
    dedup_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    @field_validator("evidence_dir", "report_dir", mode="before")
    @classmethod
    def _expand_path(cls, v: Any) -> Path:
        return Path(v).expanduser().resolve()

    @model_validator(mode="after")
    def _validate_llm_keys(self) -> "Settings":
        if self.llm_provider == LLMProvider.GOOGLE and not self.google_api_key:
            raise ValueError(
                "A11Y_GOOGLE_API_KEY must be set when llm_provider=google. "
                "Add it to your .env file — never commit secrets to git."
            )
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            raise ValueError(
                "A11Y_OPENAI_API_KEY must be set when llm_provider=openai."
            )
        return self

    def ensure_directories(self) -> None:
        """Create output directories if they do not exist."""
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton — import ``settings`` throughout the codebase.
settings = Settings()
