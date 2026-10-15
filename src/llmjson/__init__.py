"""llmjson: extract and repair JSON from messy LLM output.

>>> from llmjson import loads
>>> loads('Sure! ```json\\n{"ok": true,}\\n```')
{'ok': True}
"""

from .extract import LLMJSONError, extract, extract_all, find, loads, strip_reasoning
from .repair import repair

__version__ = "0.1.0"

__all__ = [
    "LLMJSONError",
    "extract",
    "extract_all",
    "find",
    "loads",
    "repair",
    "strip_reasoning",
    "__version__",
]
