import json

import pytest
from google.genai import errors

from pipeline import extraction
from pipeline.extraction import ExtractionError, extract_page, _parse_json

VALID_JSON = json.dumps({"po_number": "PO-9", "line_items": []})


class FakeUsage:
    def __init__(self, prompt_tokens=10, output_tokens=5):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = output_tokens
        self.total_token_count = prompt_tokens + output_tokens


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = FakeUsage()


class FakeModels:
    """Yields queued responses; exceptions in the queue are raised."""

    def __init__(self, queue):
        self.queue = list(queue)
        self.calls = []
        self.configs = []

    def generate_content(self, model, contents, config):
        self.calls.append(contents)
        self.configs.append(config)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


class FakeClient:
    def __init__(self, queue):
        self.models = FakeModels(queue)


def _api_error(code):
    # Bypass __init__ (its signature varies across SDK versions).
    error = errors.APIError.__new__(errors.APIError)
    error.code = code
    error.args = (f"HTTP {code}",)
    return error


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(extraction.time, "sleep", lambda seconds: None)


def test_parse_json_strips_markdown_fences():
    assert _parse_json(f"```json\n{VALID_JSON}\n```") == json.loads(VALID_JSON)
    assert _parse_json(VALID_JSON) == json.loads(VALID_JSON)


def test_parse_json_rejects_non_object():
    with pytest.raises(json.JSONDecodeError):
        _parse_json("[1, 2, 3]")


def test_extract_page_happy_path():
    client = FakeClient([VALID_JSON])
    result, usage = extract_page(client, image=None, model_id="test-model")
    assert result["po_number"] == "PO-9"
    assert len(client.models.calls) == 1
    assert usage.prompt_tokens == 10
    assert usage.output_tokens == 5
    assert usage.total_tokens == 15


def test_structured_output_config_is_used():
    client = FakeClient([VALID_JSON])
    extract_page(client, image=None, model_id="test-model")
    cfg = client.models.configs[0]
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema is extraction.ExtractedPO
    assert cfg.temperature == 0


def test_response_schema_field_descriptions_guard_names():
    # The company_name description is the mechanism that keeps addresses and
    # codes out of the name field — make sure it survives schema generation.
    schema = extraction.ExtractedParty.model_json_schema()
    description = schema["properties"]["company_name"]["description"]
    assert "Never a street address" in description
    assert "customer_number" in schema["properties"]


def test_invalid_json_triggers_one_clarifying_retry():
    client = FakeClient(["I am not JSON, sorry!", VALID_JSON])
    result, usage = extract_page(client, image=None, model_id="test-model")
    assert result["po_number"] == "PO-9"
    assert len(client.models.calls) == 2
    # The clarifying prompt is appended on the retry call.
    assert extraction.CLARIFY_PROMPT in client.models.calls[1]
    # Usage accumulates across both calls (the invalid-JSON attempt still cost tokens).
    assert usage.total_tokens == 30


def test_invalid_json_twice_raises_extraction_error():
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(ExtractionError, match="not valid JSON"):
        extract_page(client, image=None, model_id="test-model")


def test_retryable_api_error_backs_off_then_succeeds():
    client = FakeClient([_api_error(429), _api_error(500), VALID_JSON])
    result, usage = extract_page(client, image=None, model_id="test-model")
    assert result["po_number"] == "PO-9"
    assert len(client.models.calls) == 3
    assert usage.total_tokens == 15


def test_persistent_api_error_raises_after_max_retries():
    client = FakeClient([_api_error(429)] * 5)
    with pytest.raises(ExtractionError, match="failed after retries"):
        extract_page(client, image=None, model_id="test-model")
    assert len(client.models.calls) == 3  # MAX_API_RETRIES


def test_non_retryable_api_error_fails_fast():
    client = FakeClient([_api_error(403)])
    with pytest.raises(ExtractionError):
        extract_page(client, image=None, model_id="test-model")
    assert len(client.models.calls) == 1
