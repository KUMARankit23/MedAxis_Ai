"""
MedAxis — Startup secrets/config validation.

Usage:
    from config_validator import require_env, validate_all

    validate_all({
        "DATABASE_URL": {"min_length": 10},
        "JWT_SECRET":   {"min_length": 32},
        "REDIS_HOST":   {},
    })
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)


def require_env(name: str, min_length: int = 1) -> str:
    """
    Return the value of an environment variable.
    Exits the process with a descriptive error if missing or too short.
    Never logs the secret value itself.
    """
    value = os.getenv(name, "").strip()
    if not value:
        logger.error(
            f"STARTUP FAILURE: Required environment variable '{name}' is not set. "
            f"Check your .env file or container environment."
        )
        sys.exit(1)
    if len(value) < min_length:
        logger.error(
            f"STARTUP FAILURE: Environment variable '{name}' must be at least "
            f"{min_length} characters long. Current length: {len(value)}."
        )
        sys.exit(1)
    return value


def validate_all(spec: dict) -> None:
    """
    Validate multiple environment variables at once.

    spec format:
        {
            "VAR_NAME": {"min_length": N, "optional": True/False},
            ...
        }
    """
    errors = []
    for name, opts in spec.items():
        optional = opts.get("optional", False)
        min_len = opts.get("min_length", 1)
        value = os.getenv(name, "").strip()

        if not value:
            if not optional:
                errors.append(f"  - '{name}' is required but not set")
        elif len(value) < min_len:
            errors.append(
                f"  - '{name}' must be at least {min_len} characters "
                f"(currently {len(value)})"
            )

    if errors:
        logger.error(
            "STARTUP FAILURE: Missing or invalid environment variables:\n"
            + "\n".join(errors)
            + "\n\nCheck your .env file. See .env.example for reference."
        )
        sys.exit(1)
