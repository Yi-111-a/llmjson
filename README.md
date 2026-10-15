# llmjson

[![CI](https://github.com/Yi-111-a/llmjson/actions/workflows/ci.yml/badge.svg)](https://github.com/Yi-111-a/llmjson/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.9%E2%80%933.13-blue)
![deps](https://img.shields.io/badge/dependencies-0-brightgreen)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Extract and repair JSON from messy LLM output.** One tiny, zero-dependency
Python library + CLI that turns this:

````text
<think>
The user wants the cities as JSON. Maybe {"cities": ["Paris"]}? No, they asked for three...
</think>

Sure! Here are three cities:

```json
{
  "cities": [
    {"name": "Paris", "country": "FR"},
    {"name": "Kuala Lumpur", "country": "MY"},
    {"name": "Lima", "country": "PE"},
  ],
}
```

Let me know if you need more.
````

into this:

```console
$ llmjson --raw examples/deepseek_r1.txt
{"cities":[{"name":"Paris","country":"FR"},{"name":"Kuala Lumpur","country":"MY"},{"name":"Lima","country":"PE"}]}
```

No regexes to copy-paste between projects, no `json.loads` crash at 3 a.m.
because a model added "Sure! Here's the JSON:" or hit `max_tokens` mid-object.

## What it handles

| Problem in the model output | What llmjson does |
| --- | --- |
| ```` ```json ```` / ```` ``` ```` fences (also unterminated) | uses the fenced block; `json`-tagged fences win |
| `<think>`, `<thinking>`, `<reasoning>`, `<reflection>`, `<scratchpad>`, `<analysis>` blocks, orphan `</think>` | ignored, so a draft inside the reasoning is never picked |
| prose before / after (`Sure! ... hope this helps`) | finds the JSON span (string-aware bracket matching); the longest valid span wins over `[1]`-style citations |
| trailing commas `[1, 2,]`, `{"a": 1,}` | removed |
| `//`, `#`, `/* */` comments | removed |
| single quotes, `True` / `False` / `None` | converted to JSON |
| raw newlines / tabs inside strings, BOM, control bytes | escaped / stripped |
| mismatched closer `[1, 2}` | fixed |
| **truncated output** (`max_tokens`) | closes the open string, drops a dangling key / `,`, completes `tr`→`true`, closes all brackets |
| a refusal / no JSON at all | raises `LLMJSONError` (CLI exit code `1`) — never invents data |

Valid JSON always passes through unchanged. Repairs are applied only outside
string literals, so content like `"https://x//y"` or `"a, ]"` is never touched.

## Install

```bash
pip install git+https://github.com/Yi-111-a/llmjson@v0.1.0
# or just copy src/llmjson/ into your project: it is pure stdlib
```

Requires Python 3.9+. No dependencies.

## CLI

```console
$ cat reply.txt | llmjson            # pretty-printed (indent 2)
$ llmjson --raw reply.txt            # compact, one line (great for jq)
$ llmjson --indent 4 reply.txt
$ llmjson --strict reply.txt         # extract from fences/prose, but refuse to repair
$ llmjson --repair-only reply.txt    # print the repaired snippet text, don't parse
$ llmjson --find reply.txt           # print the raw snippet that would be parsed
$ llmjson --all reply.txt            # every JSON value found, as JSON Lines
```

Terminal demo:

```console
$ llmjson -r examples/truncated.txt          # output cut off by max_tokens
{"invoice":"INV-0042","items":[{"sku":"A1","qty":2},{"sku":"B7","qty":1,"note":"gift wr"}]}

$ llmjson -r examples/python_style.txt       # Python dict + comment + trailing comma
{"ok":true,"error":null,"tags":["a","b"]}

$ echo 'Sure: {"a": [1, 2,' | llmjson --repair-only
{"a": [1, 2]}

$ llmjson --strict examples/deepseek_r1.txt
llmjson: found JSON-like text but could not parse it: Illegal trailing comma before end of array: line 5 column 38 (char 140)
$ echo $?
1

$ llmjson examples/refusal.txt
llmjson: no JSON object or array found in input
$ echo $?
1
```

Exit status: `0` JSON recovered, `1` nothing recoverable (message on stderr), `2` usage error.
That makes it easy to use in shell pipelines:

```bash
my-llm-cli "List 3 cities as JSON" | llmjson --raw | jq -r '.cities[].name'
```

## Library

```python
from llmjson import loads, extract, extract_all, find, repair, strip_reasoning, LLMJSONError

data = loads(model_reply)                 # extract + repair + json.loads
data = loads(model_reply, strict=True)    # no repairs, valid JSON only
data = loads(model_reply, parse_float=Decimal)   # json.loads kwargs pass through

find(model_reply)        # -> the raw snippet that loads() parsed (str)
extract_all(reply)       # -> every object/array: all fenced blocks, else all top-level spans
repair('{"a": [1, 2,')   # -> '{"a": [1, 2]}'   (text in, text out)
strip_reasoning(reply)   # -> reply without <think>...</think> blocks

try:
    loads("I'm sorry, I can't help with that.")
except LLMJSONError as e:   # subclass of ValueError
    ...
```

`loads` accepts `str` or `bytes` and only returns an **object or array** (a bare
`42` or `"text"` is not treated as an answer).

### How a value is chosen

1. `<think>`-style blocks are removed (the original text is used only if the
   answer itself contains nothing JSON-like).
2. Fenced blocks tagged `json`/`jsonc`/`json5`/`js`, then untagged fences: the first one that parses wins.
3. Otherwise top-level `{...}` / `[...]` spans in the prose: the longest one that
   parses wins. A broken span is consumed whole, so llmjson never hands you a
   random inner fragment of a document it could not repair.
4. An unclosed opener is treated as truncated output and closed.

## Scope and alternatives

llmjson is deliberately small and conservative: it fixes the mistakes LLMs
actually make and refuses the rest. If you need aggressive, heuristic repair of
badly broken documents, look at [json_repair](https://github.com/mangiucugna/json_repair).
If you control the API call, prefer the provider's structured-output / JSON mode
and keep llmjson as the safety net for everything else (local models, proxies,
logs, agent transcripts).

## Development

```bash
python -m pip install -e . pytest ruff
pytest -q
ruff check src tests
```

## 中文说明

**llmjson**：从大模型的“乱七八糟”输出里提取并修复 JSON 的零依赖 Python 库 + 命令行工具。

- 自动识别 ```` ```json ```` 代码块，忽略 `<think>` / `<reasoning>` 等思考内容，跳过前后的客套话；
- 轻量修复：去掉尾逗号和注释、单引号转双引号、`True/False/None` 转 JSON、字符串内换行转义；
- 输出被 `max_tokens` 截断时自动补全字符串和括号；
- 完全没有 JSON（例如模型拒答）时报错退出（退出码 1），绝不编造数据；`--strict` 只提取、不修复。

```bash
pip install git+https://github.com/Yi-111-a/llmjson@v0.1.0
cat 模型输出.txt | llmjson --raw | jq .
```

```python
from llmjson import loads
data = loads(model_reply)
```

## License

[MIT](LICENSE)
