import json

import pytest

from llmjson import LLMJSONError, extract, extract_all, find, loads, strip_reasoning


def test_plain_object_and_array():
    assert loads('{"a": 1, "b": [true, null]}') == {"a": 1, "b": [True, None]}
    assert loads("[1, 2, 3]") == [1, 2, 3]


def test_bytes_input():
    assert loads(b'\xef\xbb\xbf{"a": "\xc3\xa9"}') == {"a": "é"}


def test_type_error():
    with pytest.raises(TypeError):
        loads(42)


def test_json_fence():
    text = 'Here is the result:\n\n```json\n{"name": "Ada", "age": 36}\n```\n\nLet me know!'
    assert loads(text) == {"name": "Ada", "age": 36}


def test_untagged_fence_and_fence_with_info_string():
    assert loads('```\n[1, 2]\n```') == [1, 2]
    assert loads('```json title="out.json"\n{"x": 1}\n```') == {"x": 1}


def test_json_fence_preferred_over_other_fences():
    text = '```python\nd = {"py": 1}\n```\n```json\n{"answer": 2}\n```'
    assert loads(text) == {"answer": 2}


def test_unterminated_fence():
    assert loads('```json\n{"a": [1, 2') == {"a": [1, 2]}


def test_think_tags_are_ignored():
    text = '<think>Maybe {"draft": true}? No, the user wants more.</think>\n{"final": true}'
    assert loads(text) == {"final": True}


@pytest.mark.parametrize("tag", ["thinking", "reasoning", "reflection", "scratchpad", "THINK"])
def test_other_reasoning_tags(tag):
    text = '<%s>{"draft": 1, "long": "xxxxxxxxxxxxxxxxxxxx"}</%s> {"final": 2}' % (tag, tag)
    assert loads(text) == {"final": 2}


def test_orphan_closing_think_tag():
    text = 'Let me consider {"draft": 1, "padding": "zzzzzzzzzzzz"}...\n</think>\n\n{"final": 3}'
    assert loads(text) == {"final": 3}


def test_json_only_inside_think_is_still_found():
    assert loads('<think>{"only": "here"}</think> sorry, no answer') == {"only": "here"}


def test_prose_wrapped():
    text = 'Sure! The extracted entities are {"people": ["Ann", "Bo"]} — hope that helps.'
    assert loads(text) == {"people": ["Ann", "Bo"]}


def test_longest_span_wins_over_citation_brackets():
    text = 'According to [1], the answer is {"value": 42, "source": [1]}.'
    assert loads(text) == {"value": 42, "source": [1]}


def test_braces_inside_strings_do_not_confuse_scanner():
    text = 'Result: {"template": "Hello {name}!", "arr": "[not, an, array"} end'
    assert loads(text) == {"template": "Hello {name}!", "arr": "[not, an, array"}


def test_trailing_commas():
    assert loads('{"a": [1, 2, 3,], "b": {"c": 1,},}') == {"a": [1, 2, 3], "b": {"c": 1}}


def test_lightly_truncated():
    assert loads('{"items": [{"id": 1}, {"id": 2') == {"items": [{"id": 1}, {"id": 2}]}
    assert loads('Output: {"msg": "the quick brown') == {"msg": "the quick brown"}


def test_strict_refuses_repair():
    with pytest.raises(LLMJSONError):
        loads('{"a": 1,}', strict=True)
    assert loads('```json\n{"a": 1}\n```', strict=True) == {"a": 1}


def test_invalid_input_fails():
    with pytest.raises(LLMJSONError, match="no JSON"):
        loads("I'm sorry, I can't help with that.")
    with pytest.raises(LLMJSONError):
        loads("")


def test_error_is_value_error():
    with pytest.raises(ValueError):
        loads("nothing")


def test_scalars_are_not_accepted():
    with pytest.raises(LLMJSONError):
        loads("```json\n42\n```")


def test_json_kwargs_forwarded():
    from decimal import Decimal

    assert loads('{"p": 1.10}', parse_float=Decimal) == {"p": Decimal("1.10")}


def test_extract_and_find():
    text = 'ok: ```json\n{"a": 1,}\n```'
    assert extract(text) == {"a": 1}
    assert find(text) == '{"a": 1,}'


def test_extract_all_fences_and_spans():
    text = '```json\n{"a": 1}\n```\nand\n```json\n[2, 3,]\n```'
    assert extract_all(text) == [{"a": 1}, [2, 3]]
    assert extract_all('one {"a": 1} two {"b": 2} three') == [{"a": 1}, {"b": 2}]
    assert extract_all("nothing here") == []


def test_strip_reasoning():
    assert strip_reasoning("<think>x</think>y") == "y"
    assert strip_reasoning("a</think>b") == "b"


def test_fence_beats_bare_span():
    assert loads('pre {"s": 1, "long": "xxxxxxxxxxxx"} ```json\n{"f": 1}\n```') == {"f": 1}


def test_broken_document_does_not_return_a_fragment():
    text = '{"outer": [{"id": 1}, {"id": 2}] @@@ garbage}'
    with pytest.raises(LLMJSONError):
        loads(text)


def test_strict_does_not_fall_back_to_inner_objects():
    text = '```json\n{"items": [{"a": 1}, {"b": 2},],}\n```'
    with pytest.raises(LLMJSONError):
        loads(text, strict=True)
    assert loads(text) == {"items": [{"a": 1}, {"b": 2}]}


def test_unclosed_prose_bracket_before_json():
    assert loads('[note: answer follows {"a": 1}') == {"a": 1}


def test_truncated_with_trailing_newline():
    assert loads('{"note": "gift wr\n') == {"note": "gift wr"}


def test_python_hash_comment():
    assert loads("{'ok': True, 'tags': ['a', 'b',], # trailing\n}") == {"ok": True, "tags": ["a", "b"]}


def test_many_openers_is_bounded():
    text = "{" * 5000 + "oops"
    with pytest.raises(LLMJSONError):
        loads(text, strict=True)


def test_roundtrip_large_valid_document():
    doc = {"rows": [{"i": i, "s": "v%d" % i, "f": i / 3} for i in range(500)]}
    assert loads("Answer:\n" + json.dumps(doc) + "\nDone.") == doc


def test_strict_failure_does_not_fall_back_to_think_block():
    text = '<think>draft {"cities": ["Paris"]}</think>\n```json\n{"cities": ["Paris", "Lima",],}\n```'
    with pytest.raises(LLMJSONError):
        loads(text, strict=True)
    assert loads(text) == {"cities": ["Paris", "Lima"]}


def test_absurd_nesting_fails_cleanly():
    with pytest.raises(LLMJSONError):
        loads("[" * 200000)
