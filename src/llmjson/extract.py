"""Locate the JSON value inside messy LLM output and parse it."""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, List, Optional, Tuple

from .repair import repair

__all__ = ["LLMJSONError", "extract", "extract_all", "find", "loads", "strip_reasoning"]

#: Tags that wrap model "thinking" which should never be mistaken for the answer.
REASONING_TAGS = ("think", "thinking", "thought", "reasoning", "reflection", "scratchpad", "analysis")

_TAGS = "|".join(REASONING_TAGS)
_REASONING_BLOCK = re.compile(r"<(%s)\b[^>]*>.*?</\1\s*>" % _TAGS, re.S | re.I)
_ORPHAN_CLOSE = re.compile(r"^.*?</(?:%s)\s*>" % _TAGS, re.S | re.I)
_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+.-]*)[^\n]*\n(.*?)(?:\n[ \t]*```|```|\Z)", re.S)
_JSON_LANGS = {"json", "jsonc", "json5", "jsonl", "javascript", "js"}
_MAX_OPENERS = 256


class LLMJSONError(ValueError):
    """Raised when no JSON object/array can be recovered from the text."""


def strip_reasoning(text: str) -> str:
    """Remove ``<think>...</think>``-style blocks (and an orphan closing tag's prefix)."""
    out = _REASONING_BLOCK.sub("", text)
    # Some models (e.g. DeepSeek-R1 templates) emit only the closing tag.
    return _ORPHAN_CLOSE.sub("", out, count=1)


_OPENER_RE = re.compile(r"[{\[]")


def _span_end(text: str, i: int) -> int:
    """Index just past the bracket that closes ``text[i]``, or -1 if it never closes.

    String-aware for double quotes; bracket kinds are not matched here (the
    repairer fixes mismatches).
    """
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def _closed_inner_spans(text: str, i: int) -> List[Tuple[int, int]]:
    """Outermost complete bracket spans after the unclosed opener at ``i`` (single O(n) pass)."""
    stack: List[int] = []
    spans: List[Tuple[int, int]] = []
    in_str = False
    esc = False
    for j in range(i + 1, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "{[":
            stack.append(j)
        elif c in "}]" and stack:
            start = stack.pop()
            while spans and spans[-1][0] > start:
                spans.pop()  # drop spans nested inside this one
            spans.append((start, j + 1))
    return spans


def _parse(snippet: str, strict: bool, **kw: Any) -> Tuple[bool, Any, Optional[str]]:
    """Parse ``snippet`` (repairing unless strict); only objects/arrays count."""
    try:
        value = json.loads(snippet, **kw)
    except (ValueError, RecursionError) as e:
        if strict:
            return False, None, str(e)
        try:
            value = json.loads(repair(snippet), **kw)
        except (ValueError, RecursionError) as e2:
            return False, None, str(e2)
    if not isinstance(value, (dict, list)):
        return False, None, "top-level value is a %s, not an object or array" % type(value).__name__
    return True, value, None


def _walk_spans(text: str, strict: bool, **kw: Any) -> Iterator[Tuple[bool, Any, str, Optional[str]]]:
    """Try top-level ``{...}`` / ``[...]`` spans left to right.

    Yields ``(ok, value, snippet, error)``. A complete span is consumed whole
    whether or not it parses, so fragments of a broken document are never
    returned. An opener that never closes is treated as truncated JSON running
    to the end of the text; if that cannot be repaired the scan moves on to
    the next opener.
    """
    i = 0
    tried = 0
    while tried < _MAX_OPENERS:
        m = _OPENER_RE.search(text, i)
        if m is None:
            return
        i = m.start()
        tried += 1
        end = _span_end(text, i)
        if end < 0:
            snippet = text[i:].rstrip()
            ok, value, err = _parse(snippet, strict, **kw)
            yield ok, value, snippet, err
            if not ok:
                # e.g. "[note: answer follows {...}": try the complete spans inside, then stop
                for a, b in _closed_inner_spans(text, i)[:_MAX_OPENERS]:
                    ok, value, err = _parse(text[a:b], strict, **kw)
                    yield ok, value, text[a:b], err
            return
        snippet = text[i:end]
        ok, value, err = _parse(snippet, strict, **kw)
        yield ok, value, snippet, err
        i = end


def _fences(text: str) -> List[str]:
    tagged: List[str] = []
    untagged: List[str] = []
    for m in _FENCE.finditer(text):
        lang = m.group(1).lower()
        body = m.group(2).strip()
        if not body:
            continue
        if lang in _JSON_LANGS:
            tagged.append(body)
        elif lang == "":
            untagged.append(body)
    return tagged + untagged


def _coerce(text: Any) -> str:
    if isinstance(text, str):
        return text
    if isinstance(text, (bytes, bytearray)):
        return bytes(text).decode("utf-8", errors="replace")
    raise TypeError("expected str or bytes, got %s" % type(text).__name__)


def _sources(text: str) -> List[str]:
    """The reasoning-stripped text first, then the original (used only if the first has no JSON-like text)."""
    cleaned = strip_reasoning(text)
    return [cleaned] if cleaned == text else [cleaned, text]


def _search(text: Any, strict: bool, **kw: Any) -> Tuple[Any, str]:
    text = _coerce(text)
    first_err: Optional[str] = None
    seen_any = False
    for src in _sources(text):
        # 1. fenced code blocks: the first one that parses wins
        for body in _fences(src):
            seen_any = True
            ok, value, err = _parse(body, strict, **kw)
            if ok:
                return value, body
            first_err = first_err or err
        # 2. bare spans in prose: the longest one that parses wins ("see [1]" vs the real object)
        best: Optional[Tuple[Any, str]] = None
        for ok, value, snippet, err in _walk_spans(src, strict, **kw):
            seen_any = True
            if ok:
                if best is None or len(snippet) > len(best[1]):
                    best = (value, snippet)
            else:
                first_err = first_err or err
        if best is not None:
            return best
        if seen_any:
            break  # the answer had JSON-like text; never fall back to the reasoning block
    if not seen_any:
        raise LLMJSONError("no JSON object or array found in input")
    raise LLMJSONError("found JSON-like text but could not parse it: %s" % first_err)


def loads(text: str, *, strict: bool = False, **json_kwargs: Any) -> Any:
    """Extract, repair and parse the JSON object/array contained in ``text``.

    ``strict=True`` disables repairs (extraction from fences/prose still applies).
    Extra keyword arguments are forwarded to :func:`json.loads`.
    Raises :class:`LLMJSONError` (a ``ValueError``) on failure.
    """
    return _search(text, strict, **json_kwargs)[0]


def extract(text: str, *, strict: bool = False) -> Any:
    """Same as :func:`loads` but without ``json.loads`` keyword arguments."""
    return _search(text, strict)[0]


def find(text: str, *, strict: bool = False) -> str:
    """Return the raw (unrepaired) snippet that :func:`loads` would parse."""
    return _search(text, strict)[1]


def extract_all(text: str, *, strict: bool = False) -> List[Any]:
    """Return every JSON object/array found: all fenced blocks if any parse, else all top-level spans."""
    cleaned = strip_reasoning(_coerce(text))
    results: List[Any] = []
    for body in _fences(cleaned):
        ok, value, _ = _parse(body, strict)
        if ok:
            results.append(value)
    if results:
        return results
    return [value for ok, value, _, _ in _walk_spans(cleaned, strict) if ok]
