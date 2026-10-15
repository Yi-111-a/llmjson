import json

import pytest

from llmjson import repair


@pytest.mark.parametrize(
    "doc",
    [
        {},
        [],
        {"a": "b, ] } // not a comment", "n": -1.5e3, "t": True, "f": False, "z": None},
        [1, "two", [3, [4]], {"five": 5}],
        {"unicode": "中文 ✓", "esc": "quote \" backslash \\ newline \n tab \t"},
        {"url": "https://example.com/a//b/*c*/"},
    ],
)
def test_valid_json_is_unchanged(doc):
    for text in (json.dumps(doc), json.dumps(doc, indent=2), json.dumps(doc, ensure_ascii=False)):
        assert repair(text) == text


def test_bom_and_control_chars():
    assert json.loads(repair('\ufeff{"a":\x00 1}')) == {"a": 1}


def test_trailing_commas():
    assert repair('{"a": 1,}') == '{"a": 1}'
    assert repair("[1, 2,\n]") == "[1, 2\n]"


def test_comments():
    text = '{\n  // the id\n  "id": 7, /* inline */ "ok": true\n}'
    assert json.loads(repair(text)) == {"id": 7, "ok": True}


def test_single_quotes_and_python_literals():
    assert json.loads(repair("{'a': 'it\\'s', 'b': True, 'c': None, 'd': False}")) == {
        "a": "it's",
        "b": True,
        "c": None,
        "d": False,
    }
    assert json.loads(repair("{'say': 'he said \"hi\"'}")) == {"say": 'he said "hi"'}


def test_raw_newlines_inside_strings():
    assert json.loads(repair('{"poem": "line one\nline two\tend"}')) == {"poem": "line one\nline two\tend"}


def test_mismatched_closer():
    assert json.loads(repair('{"a": [1, 2}')) == {"a": [1, 2]}
    assert json.loads(repair('[1, 2]]')) == [1, 2]


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"a": 1', {"a": 1}),
        ('{"a": [1, 2', {"a": [1, 2]}),
        ('{"a": "unfinished', {"a": "unfinished"}),
        ('{"a": 1,', {"a": 1}),
        ('{"a": 1, "b":', {"a": 1, "b": None}),
        ('{"a": 1, "b"', {"a": 1}),
        ('{"a": 1, "b": tr', {"a": 1, "b": True}),
        ('{"a": [fal', {"a": [False]}),
        ('{"a": 1.', {"a": 1}),
        ('{"a": 2e-', {"a": 2}),
        ('[1, -', [1]),
        ('{"a": "x\\', {"a": "x"}),
        ('{"k": "v,"', {"k": "v,"}),
    ],
)
def test_truncation(text, expected):
    assert json.loads(repair(text)) == expected


def test_non_json_words_left_alone():
    assert repair("[hello]") == "[hello]"
