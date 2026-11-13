import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lang_handler.api import OpenAIService, ServiceError


def test_canvas_uses_vision_input_and_never_response_storage():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output_text='{"items": [" カフェ ", "カフエ"]}'
    )
    service = OpenAIService("test-only", client=client)
    png = b"\x89PNG\r\n\x1a\ncanvas-test"
    assert service.recognize_handwriting(png, "gpt-6-luna", "Japanese katakana") == [
        "カフェ",
        "カフエ",
    ]
    payload = client.responses.create.call_args.kwargs
    assert payload["store"] is False
    assert payload["reasoning"] == {"effort": "medium"}
    image = payload["input"][0]["content"][0]
    assert image["type"] == "input_image"
    assert base64.b64decode(image["image_url"].split(",", 1)[1]) == png
    assert "Japanese katakana" not in payload["instructions"]
    assert json.loads(payload["input"][0]["content"][1]["text"]) == {
        "custom_instructions": "Japanese katakana"
    }


def test_invalid_canvas_rejected_before_network():
    client = Mock()
    service = OpenAIService("test-only", client=client)
    with pytest.raises(ServiceError, match="valid canvas PNG"):
        service.recognize_handwriting(b"not-png", "gpt-6-luna")
    client.responses.create.assert_not_called()


def test_canvas_returns_distinct_nonempty_candidates():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        output_text='{"items": [" わ ", "わ", "", "ね", "れ"]}'
    )
    result = OpenAIService("test-only", client=client).recognize_handwriting(
        b"\x89PNG\r\n\x1a\ncanvas-test", "gpt-6-luna"
    )
    assert result == ["わ", "ね", "れ"]
    schema = client.responses.create.call_args.kwargs["text"]["format"]
    assert schema["type"] == "json_schema"
    assert schema["strict"] is True
    assert schema["schema"]["properties"]["items"]["type"] == "array"
    assert "minItems" not in schema["schema"]["properties"]["items"]


@pytest.mark.parametrize("result", ['{"items": []}', '{"items": [" "]}'])
def test_unreadable_canvas_returns_empty_list(result):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text=result)
    assert (
        OpenAIService("test-only", client=client).recognize_handwriting(
            b"\x89PNG\r\n\x1a\ncanvas-test", "gpt-6-luna"
        )
        == []
    )


@pytest.mark.parametrize("result", ["plain text", "[]", '{"items": "text"}', '{"items": [3]}'])
def test_malformed_candidates_are_rejected(result):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text=result)
    with pytest.raises(ServiceError, match="invalid handwriting result"):
        OpenAIService("test-only", client=client).recognize_handwriting(
            b"\x89PNG\r\n\x1a\ncanvas-test", "gpt-6-luna"
        )


def test_canvas_language_and_reasoning_are_sent_to_the_model():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text='{"items": ["カフェ"]}')
    result = OpenAIService("test-only", client=client).recognize_handwriting(
        b"\x89PNG\r\n\x1a\ncanvas-test", "gpt-6-luna", reasoning="high", language="ja"
    )
    assert result == ["カフェ"]
    payload = client.responses.create.call_args.kwargs
    assert payload["reasoning"] == {"effort": "high"}
    assert "Expected handwriting language: ja" in payload["instructions"]


def test_auto_handwriting_language_does_not_force_a_language():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text='{"items": ["café"]}')
    OpenAIService("test-only", client=client).recognize_handwriting(
        b"\x89PNG\r\n\x1a\ncanvas-test", "gpt-4.1", language=""
    )
    payload = client.responses.create.call_args.kwargs
    assert "reasoning" not in payload
    assert "Expected handwriting language" not in payload["instructions"]
