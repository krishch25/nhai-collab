"""Centralised logging configuration."""

from __future__ import annotations

import logging
from logging.config import dictConfig

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure standard logging for the application."""

    settings = get_settings()
    level = logging.DEBUG if settings.env == "dev" else logging.INFO

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                },
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
        }
    )

