"""Light, conservative repairs for almost-JSON text produced by LLMs.

The repairer is a single left-to-right scanner that understands JSON strings,
so it never touches characters inside a string literal (apart from escaping
raw control characters, which JSON forbids). Valid JSON passes through
unchanged.
"""

from __future__ import annotations

import re

__all__ = ["repair"]

_CLOSER = {"{": "}", "[": "]"}
_OPENER = {"}": "{", "]": "["}
_WORD_MAP = {"True": "true", "False": "false", "None": "null"}
_LITERALS = ("true", "false", "null")
_DANGLING_KEY = re.compile(r'([{,])\s*"(?:[^"\\]|\\.)*"\s*$', re.S)


def _strip_trailing_comma(out: list) -> None:
    """Remove a ',' that is followed only by whitespace at the end of ``out``."""
    ws = []
    while out and out[-1].isspace():
        ws.append(out.pop())
    if out and out[-1] == ",":
        out.pop()
    out.extend(reversed(ws))


def repair(text: str) -> str:
    """Return ``text`` with common LLM JSON mistakes fixed.

    Repairs applied (outside string literals unless noted):

    * remove a byte-order mark and stray control characters
    * drop ``//``, ``#`` and ``/* */`` comments
    * drop trailing commas before ``}`` / ``]``
    * convert single-quoted strings to double-quoted strings
    * map Python literals ``True`` / ``False`` / ``None`` to JSON
    * inside strings: escape raw newlines, tabs and carriage returns
    * insert missing closers when brackets are mismatched (``[1, 2}``)
    * close a truncated document: unterminated string, dangling ``,``/``:``,
      half-written ``true``/``false``/``null`` and unclosed brackets

    The result is not guaranteed to be valid JSON; it is the best light-touch
    attempt. Use :func:`llmjson.loads` to repair *and* parse.
    """
    s = text.replace("\ufeff", "")
    n = len(s)
    out: list = []
    stack: list = []
    in_str = False
    quote = '"'
    i = 0
    while i < n:
        c = s[i]
        if in_str:
            if c == "\\":
                nxt = s[i + 1] if i + 1 < n else ""
                if nxt == "":
                    i += 1  # dangling backslash at EOF: drop it
                    continue
                if quote == "'" and nxt == "'":
                    out.append("'")
                else:
                    out.append(c + nxt)
                i += 2
                continue
            if c == quote:
                out.append('"')
                in_str = False
            elif c == '"':  # bare double quote inside a single-quoted string
                out.append('\\"')
            elif c == "\n":
                out.append("\\n")
            elif c == "\r":
                out.append("\\r")
            elif c == "\t":
                out.append("\\t")
            elif ord(c) < 0x20:
                pass
            else:
                out.append(c)
            i += 1
            continue

        if c == '"' or c == "'":
            in_str = True
            quote = c
            out.append('"')
        elif c == "#" or (c == "/" and s.startswith("//", i)):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        elif c == "/" and s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        elif c in "{[":
            stack.append(c)
            out.append(c)
        elif c in "}]":
            _strip_trailing_comma(out)
            want = _OPENER[c]
            if want in stack:
                while stack[-1] != want:
                    out.append(_CLOSER[stack.pop()])
                stack.pop()
                out.append(c)
            # an unmatched closer is dropped
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            out.append(_WORD_MAP.get(word, word))
            i = j
            continue
        elif ord(c) < 0x20 and c not in "\t\n\r":
            pass
        else:
            out.append(c)
        i += 1

    if not (in_str or stack):
        return "".join(out)

    # ---- the document was truncated: close it as gently as possible ----
    if in_str:
        while out and out[-1] in ("\\n", "\\r", "\\t", " "):
            out.pop()  # whitespace after a cut-off string is noise
        out.append('"')
    tail = "".join(out).rstrip()
    if not in_str:
        # half-written number: "1." / "1e" / "1e-" / lone "-"
        tail = re.sub(r"(?<=\d)(?:\.|[eE][+-]?)$", "", tail)
        tail = re.sub(r"(?<=[\s,:\[])-$", "", tail).rstrip()
        # half-written literal: "tr" -> "true"
        m = re.search(r"(?<![A-Za-z0-9_\"])([a-z]+)$", tail)
        if m:
            frag = m.group(1)
            for lit in _LITERALS:
                if lit.startswith(frag):
                    tail += lit[len(frag):]
                    break
    if stack and stack[-1] == "{":
        m = _DANGLING_KEY.search(tail)
        if m:  # a key with no value: drop it
            tail = tail[: m.start() + 1].rstrip()
    if tail.endswith(","):
        tail = tail[:-1].rstrip()
    elif tail.endswith(":"):
        tail += " null"
    return tail + "".join(_CLOSER[b] for b in reversed(stack))
