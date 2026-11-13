"""Reasoning controls for text and image-capable Responses models."""

import re

from .errors import ServiceError

REASONING_EFFORTS = ("low", "medium", "high")


def supports_reasoning(model: str) -> bool:
    # Chat aliases and specialized audio/image models do not expose this control.
    if any(part in model for part in ("chat", "audio", "realtime", "transcribe", "image")):
        return False
    return bool(re.match(r"(?:gpt-[56](?:[.-]|$)|o[134](?:-|$))", model))


def reasoning_options(model: str, effort: str = "medium") -> dict:
    if effort not in REASONING_EFFORTS:
        raise ServiceError("Choose Low, Medium, or High reasoning in this tool's settings.")
    if not supports_reasoning(model):
        return {}
    # Unlike the later Pro families, the original GPT-5 Pro only supports High.
    if (model == "gpt-5-pro" or model.startswith("gpt-5-pro-")) and effort != "high":
        raise ServiceError("GPT-5 Pro only supports High reasoning. Select High or another model.")
    return {"reasoning": {"effort": effort}}
