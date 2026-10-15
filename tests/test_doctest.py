import doctest

import llmjson


def test_package_docstring_examples():
    result = doctest.testmod(llmjson)
    assert result.attempted > 0 and result.failed == 0
