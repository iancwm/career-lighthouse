from datetime import datetime, timezone

from utils.sdk_shapes import (
    coerce_mapping,
    coerce_sequence,
    estimate_input_chars,
    estimate_output_chars,
    format_timestamp,
    get_value,
    preview_input,
    preview_output,
    truncate_preview,
)


class ModelDumpShape:
    def model_dump(self):
        return {"data": [{"id": "one"}], "name": "shape"}


class AttributeShape:
    def __init__(self):
        self.items = ["a", "b"]
        self.status = "ok"


def test_coerce_mapping_and_sequence_from_sdk_like_objects():
    assert coerce_mapping(ModelDumpShape()) == {"data": [{"id": "one"}], "name": "shape"}
    assert coerce_sequence(ModelDumpShape()) == [{"id": "one"}]
    assert coerce_sequence(AttributeShape()) == ["a", "b"]
    assert get_value(AttributeShape(), "missing", "status") == "ok"


def test_preview_and_length_helpers_match_trace_expectations():
    payload = {
        "system_chars": 10,
        "messages": [
            {"content_chars": 5, "content_preview": "older"},
            {"content_chars": 7, "content_preview": "newer"},
        ],
    }
    output = {"content": "generated answer", "content_preview": "answer"}

    assert estimate_input_chars(payload) == 22
    assert estimate_output_chars(output) == len("generated answer")
    assert preview_input(payload) == "newer"
    assert preview_output(output) == "answer"
    assert truncate_preview("abcd", limit=3) == "abc…"


def test_format_timestamp_normalizes_datetimes_to_utc():
    ts = datetime(2026, 4, 27, 1, 2, 3, tzinfo=timezone.utc)

    assert format_timestamp(ts) == "2026-04-27T01:02:03+00:00"

