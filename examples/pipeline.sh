#!/usr/bin/env sh
# Pipe any model output through llmjson, then into jq.
# Example: some-llm-cli "List 3 cities as JSON" | llmjson --raw | jq -r '.cities[].name'
set -eu
here=$(dirname "$0")
llmjson --raw "$here/deepseek_r1.txt" | python3 -c 'import json,sys; print([c["name"] for c in json.load(sys.stdin)["cities"]])'
