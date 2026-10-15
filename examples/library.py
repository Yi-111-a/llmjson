"""Library usage: python examples/library.py"""

from llmjson import LLMJSONError, extract_all, find, loads, repair

reply = open(__file__.replace("library.py", "deepseek_r1.txt"), encoding="utf-8").read()
print(loads(reply)["cities"][1]["name"])  # Kuala Lumpur
print(find(reply)[:12] + "...")  # the raw snippet that was parsed
print(repair('{"a": [1, 2,'))  # {"a": [1, 2]}
print(extract_all('first {"a": 1} then {"b": 2}'))  # [{'a': 1}, {'b': 2}]

try:
    loads('{"a": 1,}', strict=True)
except LLMJSONError as e:
    print("strict mode refused:", e)
