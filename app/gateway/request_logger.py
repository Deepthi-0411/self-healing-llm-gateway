import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from app.observability.metrics import record_event_metrics

# ============================================================
# LOGGER CONFIGURATION
# ============================================================

LOGGER_NAME = "llm_gateway"

logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(message)s")
    )
    logger.addHandler(handler)

logger.propagate = False


# ============================================================
# PII PATTERNS
# ============================================================

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

IPV4_PATTERN = re.compile(
    r"\b"
    r"(?:"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"\."
    r"){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    r"\b"
)

JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]+"
    r"\.[A-Za-z0-9_-]+"
    r"\.[A-Za-z0-9_-]+\b"
)

BEARER_PATTERN = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"
)


# ============================================================
# GEMINI API KEY
# ============================================================

# Gemini / Google API keys commonly use the AIza prefix.
GEMINI_API_KEY_PATTERN = re.compile(
    r"\bAIza[A-Za-z0-9_-]+\b"
)


# ============================================================
# PHONE NUMBER
# ============================================================

PHONE_PATTERN = re.compile(
    r"(?<![\d.])"
    r"(?:"
    r"\+\d{1,3}[\s.-]?"
    r")?"
    r"(?:"
    r"\d{10}"
    r"|"
    r"\d{5}[\s.-]\d{5}"
    r"|"
    r"\d{3}[\s.-]\d{3}[\s.-]\d{4}"
    r"|"
    r"\d{4}[\s.-]\d{3}[\s.-]\d{3}"
    r")"
    r"(?!\d)"
)


# ============================================================
# CREDIT CARD
# ============================================================

CREDIT_CARD_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\d[ -]?){13,19}"
    r"(?!\d)"
)


# ============================================================
# SENSITIVE FIELD NAMES
# ============================================================

SENSITIVE_FIELD_NAMES = {
    "api_key",
    "apikey",
    "api-token",
    "api_token",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "credential",
    "credentials",
    "cloudflare_api_token",
    "gemini_api_key",
    "cohere_api_key",
}


# ============================================================
# REDACT STRING
# ============================================================

def redact_string(value: str) -> str:
    """
    Redact PII and secrets from a string.
    """

    text = value

    # Authentication material first.
    text = BEARER_PATTERN.sub(
        "Bearer [REDACTED]",
        text,
    )

    text = JWT_PATTERN.sub(
        "[REDACTED_JWT]",
        text,
    )

    # Active Gemini provider secret format.
    text = GEMINI_API_KEY_PATTERN.sub(
        "[REDACTED_GEMINI_API_KEY]",
        text,
    )

    # Email.
    text = EMAIL_PATTERN.sub(
        "[REDACTED_EMAIL]",
        text,
    )

    # IPv4 before phone/card.
    text = IPV4_PATTERN.sub(
        "[REDACTED_IP]",
        text,
    )

    # Credit card before phone.
    text = CREDIT_CARD_PATTERN.sub(
        "[REDACTED_CARD]",
        text,
    )

    # Phone last.
    text = PHONE_PATTERN.sub(
        "[REDACTED_PHONE]",
        text,
    )

    return text


# ============================================================
# REDACT ANY VALUE
# ============================================================

def redact_pii(
    value: Any,
    field_name: str | None = None,
) -> Any:
    """
    Recursively redact PII and secret values.

    Sensitive dictionary fields are completely replaced rather
    than relying only on pattern matching.
    """

    # --------------------------------------------------------
    # Sensitive field itself
    # --------------------------------------------------------

    if field_name is not None:
        normalized_name = field_name.lower().strip()

        if normalized_name in SENSITIVE_FIELD_NAMES:
            return "[REDACTED_SECRET]"

    # --------------------------------------------------------
    # None
    # --------------------------------------------------------

    if value is None:
        return None

    # --------------------------------------------------------
    # Dictionary
    # --------------------------------------------------------

    if isinstance(value, dict):
        redacted = {}

        for key, item in value.items():

            key_string = str(key)

            redacted[key_string] = redact_pii(
                item,
                field_name=key_string,
            )

        return redacted

    # --------------------------------------------------------
    # List
    # --------------------------------------------------------

    if isinstance(value, list):
        return [
            redact_pii(item)
            for item in value
        ]

    # --------------------------------------------------------
    # Tuple
    # --------------------------------------------------------

    if isinstance(value, tuple):
        return tuple(
            redact_pii(item)
            for item in value
        )

    # --------------------------------------------------------
    # String
    # --------------------------------------------------------

    if isinstance(value, str):
        return redact_string(value)

    # --------------------------------------------------------
    # Everything else
    # --------------------------------------------------------

    return value


# ============================================================
# STRUCTURED EVENT LOGGER
# ============================================================

def log_event(
    event: str,
    level: str = "INFO",
    **fields: Any,
) -> None:
    """
    Emit one structured JSON log event after redaction.
    """

    safe_fields = redact_pii(fields)
    
    record_event_metrics(
    event=event,
    fields=safe_fields,
    )

    payload = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "level": level.upper(),

        "service": LOGGER_NAME,

        "event": redact_string(event),

        **safe_fields,
    }

    logger.info(
        json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )
    )


# ============================================================
# REQUEST START
# ============================================================

def log_request_start(
    request_id: str,
    tenant: str,
    feature: str,
    requested_model: str,
) -> None:
    """
    Log request metadata without logging prompt content.
    """

    log_event(
        "request_started",
        request_id=request_id,
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
    )


# ============================================================
# REQUEST ERROR
# ============================================================

def log_request_error(
    request_id: str,
    tenant: str,
    feature: str,
    error_type: str,
    error_message: str,
) -> None:
    """
    Log an error after PII and secret redaction.
    """

    log_event(
        "request_error",
        request_id=request_id,
        tenant=tenant,
        feature=feature,
        error_type=error_type,
        error_message=error_message,
    )