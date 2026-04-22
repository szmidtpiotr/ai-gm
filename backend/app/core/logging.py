import logging
import os
import time
from typing import Any

import structlog

PROCESS_START_TIME = time.time()


def add_service_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    event_dict["service"] = "backend"
    event_dict["env"] = os.getenv("ENV", "production")
    return event_dict


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_ai_gm_structlog_configured", False):
        return

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_service_context,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root._ai_gm_structlog_configured = True

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def reset_request_context(**values: Any) -> None:
    structlog.contextvars.clear_contextvars()
    if values:
        structlog.contextvars.bind_contextvars(**values)


def bind_context(**values: Any) -> None:
    if values:
        structlog.contextvars.bind_contextvars(**values)


def get_uptime_seconds() -> int:
    return max(0, int(time.time() - PROCESS_START_TIME))
