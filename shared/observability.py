"""
MedAxis — Shared observability: Prometheus metrics + Sentry error tracking.

Usage in each service main.py:
    from observability import setup_metrics, setup_sentry

    setup_sentry(service_name="auth-service")
    setup_metrics(app, service_name="auth-service")
"""
import os
import logging

logger = logging.getLogger(__name__)


def setup_sentry(service_name: str) -> None:
    """
    Initialize Sentry SDK if SENTRY_DSN is configured.
    Skips silently if DSN is not set — never blocks startup.
    PII scrubbing via before_send hook.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info(f"Sentry not configured for {service_name} (SENTRY_DSN not set)")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        _PII_FIELDS = {
            "password", "password_hash", "new_password", "token",
            "access_token", "refresh_token", "patient_name", "patient_phone",
            "doctor_name", "email",
        }

        def _scrub_pii(event, hint):
            """Remove PII fields from Sentry events before sending."""
            try:
                request = event.get("request", {})
                data = request.get("data", {})
                if isinstance(data, dict):
                    for field in _PII_FIELDS:
                        if field in data:
                            data[field] = "[Filtered]"
            except Exception:
                pass
            return event

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            environment=os.getenv("ENVIRONMENT", "production"),
            release=f"{service_name}@1.0.0",
            traces_sample_rate=0.1,   # 10% of transactions for performance monitoring
            before_send=_scrub_pii,
            send_default_pii=False,   # never send PII automatically
        )
        logger.info(f"Sentry initialized for {service_name}")
    except ImportError:
        logger.warning("sentry-sdk not installed — skipping Sentry setup")
    except Exception as e:
        logger.warning(f"Sentry init failed: {e} — continuing without error tracking")


def setup_metrics(app, service_name: str) -> None:
    """
    Instrument a FastAPI app with Prometheus metrics.
    Exposes /metrics endpoint (no auth required for Prometheus scraping).
    """
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            excluded_handlers=["/metrics", "/health"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

        logger.info(f"Prometheus metrics enabled for {service_name} at /metrics")
    except ImportError:
        logger.warning("prometheus-fastapi-instrumentator not installed — skipping metrics")
    except Exception as e:
        logger.warning(f"Metrics setup failed: {e}")
