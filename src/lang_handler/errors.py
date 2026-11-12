"""Safe, user-facing service errors; never show bearer tokens."""

import re


class ServiceError(RuntimeError):
    """An actionable failure safe to display in the desktop interface."""


def redact(value: str, secret: str = "") -> str:
    if secret:
        value = value.replace(secret, "[redacted]")
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", value)


def service_error(error: Exception, secret: str = "") -> ServiceError:
    if isinstance(error, ServiceError):
        return error
    code = getattr(error, "code", "") or ""
    status = getattr(error, "status_code", None)
    if status == 401:
        return ServiceError("OpenAI rejected this API key. Check or replace it in Preferences.")
    if status == 403:
        return ServiceError("This API key cannot access the requested model or service.")
    if status == 429:
        if code in {"insufficient_quota", "credit_balance_exhausted"}:
            return ServiceError(
                "OpenAI API credits are exhausted or unavailable for this key's organization."
            )
        if "limit" in code and "rate" not in code:
            return ServiceError("OpenAI's organization or project spending limit was reached.")
        return ServiceError(
            "OpenAI's request limit was reached. Wait briefly or use longer audio chunks."
        )
    if status is not None and status >= 500:
        return ServiceError("OpenAI is temporarily unavailable. Please try again shortly.")
    if status in {400, 404, 422}:
        body = getattr(error, "body", {})
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            body = body["error"]
        message = body.get("message", "") if isinstance(body, dict) else ""
        detail = redact(str(message), secret).strip()[:400]
        return ServiceError(
            detail or "Check the model and language settings; OpenAI rejected the request."
        )
    name = type(error).__name__
    if "Timeout" in name:
        return ServiceError("The OpenAI request timed out. Check your connection and try again.")
    if any(word in name for word in ("Connection", "Connect", "Proxy", "Network", "WebSocket")):
        return ServiceError(
            "Cannot connect to OpenAI. Check your internet connection and proxy settings."
        )
    # Unexpected exception messages may contain authentication headers or request data.
    return ServiceError(
        f"The OpenAI request failed ({name}). Check the selected model and try again."
    )
