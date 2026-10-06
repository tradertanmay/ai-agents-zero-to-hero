"""
Configuration, Secrets, and Environment Separation (Module 13)
Enforces: "Code != Configuration != Secrets"
Provides secret-redaction utilities for structured telemetry.
"""

from dataclasses import dataclass, field
import os
import re
from typing import Any


class ConfigurationError(Exception):
    """Raised when environment or security configuration is invalid."""
    pass


@dataclass
class AgentConfig:
    """Production runtime configuration loaded strictly from environment."""
    app_env: str = "development"
    max_steps_per_run: int = 10
    max_retries: int = 2
    approval_required: bool = True
    allowed_subreddits: set[str] = field(default_factory=lambda: {"r/Python", "r/AI_Agents"})
    log_level: str = "INFO"
    lease_duration_seconds: float = 30.0
    heartbeat_interval_seconds: float = 10.0
    # Credentials / Secrets
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    hmac_signing_secret: str = "production_safety_hmac_secret_default"

    @classmethod
    def from_env(cls, env_dict: dict[str, str] | None = None) -> "AgentConfig":
        env = env_dict if env_dict is not None else os.environ

        app_env = env.get("APP_ENV", "development").lower()
        max_steps = int(env.get("MAX_STEPS", "10"))
        max_retries = int(env.get("MAX_RETRIES", "2"))
        approval_req = env.get("APPROVAL_REQUIRED", "true").lower() in ("true", "1", "yes")

        subreddits_raw = env.get("ALLOWED_SUBREDDITS", "r/Python,r/AI_Agents")
        allowed_subreddits = {s.strip() for s in subreddits_raw.split(",") if s.strip()}

        log_level = env.get("LOG_LEVEL", "INFO").upper()
        lease_sec = float(env.get("LEASE_DURATION_SECONDS", "30.0"))
        hb_sec = float(env.get("HEARTBEAT_INTERVAL_SECONDS", "10.0"))

        client_id = env.get("REDDIT_CLIENT_ID")
        client_secret = env.get("REDDIT_CLIENT_SECRET")
        signing_secret = env.get("HMAC_SIGNING_SECRET", "production_safety_hmac_secret_default")

        # Production Validation: Required secrets must never be missing in production
        if app_env == "production":
            if not client_secret or not client_id:
                raise ConfigurationError(
                    "ProductionSecurityError: REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set when APP_ENV=production."
                )

        return cls(
            app_env=app_env,
            max_steps_per_run=max_steps,
            max_retries=max_retries,
            approval_required=approval_req,
            allowed_subreddits=allowed_subreddits,
            log_level=log_level,
            lease_duration_seconds=lease_sec,
            heartbeat_interval_seconds=hb_sec,
            reddit_client_id=client_id,
            reddit_client_secret=client_secret,
            hmac_signing_secret=signing_secret,
        )


SENSITIVE_KEY_PATTERN = re.compile(
    r"(token|secret|password|key|auth|signature|nonce|credentials)", re.IGNORECASE
)


def redact_secrets(val: Any) -> Any:
    """
    Recursively redacts sensitive values from dictionaries, lists, and strings
    to ensure secrets are never leaked into logs, metrics, or traces.
    """
    if isinstance(val, dict):
        redacted = {}
        for k, v in val.items():
            if SENSITIVE_KEY_PATTERN.search(str(k)):
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = redact_secrets(v)
        return redacted
    elif isinstance(val, list):
        return [redact_secrets(item) for item in val]
    elif isinstance(val, str):
        # Redact raw HMAC tokens or obvious secret patterns if embedded in strings
        if len(val) > 20 and ("." in val) and any(seg.isalnum() for seg in val.split(".")):
            parts = val.split(".")
            if len(parts) == 5:
                # Likely an approval capability token
                return f"{parts[0]}.***REDACTED_TOKEN***"
        return val
    return val
