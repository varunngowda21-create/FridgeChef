import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    parts = email.split("@", 1)
    name = parts[0]
    domain = parts[1]
    if len(name) <= 1:
        masked_name = "*"
    else:
        masked_name = name[0] + "***"
    return f"{masked_name}@{domain}"


EMAIL_REGEX = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b")


def sanitize_log_message(msg: str) -> str:
    # Mask any emails appearing in the message text
    return EMAIL_REGEX.sub(r"\1***@\2", msg)


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter adhering to PRD NFR-040."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": sanitize_log_message(record.getMessage()),
            "logger": record.name,
        }

        # Structured metadata fields
        for field in ("request_id", "user_id_hash", "endpoint", "status_code", "latency_ms", "error_code"):
            val = getattr(record, field, None)
            if val is not None:
                log_obj[field] = val

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers = [handler]

    # Reduce noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
