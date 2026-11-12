import base64
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lang_handler.api import OpenAIService, ServiceError


def test_canvas_uses_vision_input_and_never_response_storage():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text=" カフェ ")
    service = OpenAIService("test-only", client=client)
    png = b"\x89PNG\r\n\x1a\ncanvas-test"
    assert service.recognize_handwriting(png, "gpt-6-luna", "Japanese katakana") == "カフェ"
    payload = client.responses.create.call_args.kwargs
    assert payload["store"] is False
    image = payload["input"][0]["content"][0]
    assert image["type"] == "input_image"
    assert base64.b64decode(image["image_url"].split(",", 1)[1]) == png
    assert "Japanese katakana" in payload["instructions"]


def test_invalid_canvas_rejected_before_network():
    client = Mock()
    service = OpenAIService("test-only", client=client)
    with pytest.raises(ServiceError, match="valid canvas PNG"):
        service.recognize_handwriting(b"not-png", "gpt-6-luna")
    client.responses.create.assert_not_called()
