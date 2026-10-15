import io
import json
import subprocess
import sys

import pytest

from llmjson import cli

MESSY = '<think>hmm</think>\nSure!\n```json\n{"a": [1, 2,], "b": "x"}\n```\n'


def run(argv, stdin="", monkeypatch=None, capsys=None):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin.encode("utf-8"))))
    code = cli.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_stdin_pretty(monkeypatch, capsys):
    code, out, _ = run([], MESSY, monkeypatch, capsys)
    assert code == 0
    assert json.loads(out) == {"a": [1, 2], "b": "x"}
    assert out.startswith("{\n  ")


def test_raw_and_indent(monkeypatch, capsys):
    code, out, _ = run(["--raw", "-"], MESSY, monkeypatch, capsys)
    assert code == 0 and out == '{"a":[1,2],"b":"x"}\n'
    code, out, _ = run(["--indent", "4"], MESSY, monkeypatch, capsys)
    assert out.startswith('{\n    "a"')


def test_file_input(tmp_path, capsys):
    p = tmp_path / "reply.txt"
    p.write_text(MESSY, encoding="utf-8")
    assert cli.main(["-r", str(p)]) == 0
    assert capsys.readouterr().out == '{"a":[1,2],"b":"x"}\n'


def test_missing_file(capsys):
    assert cli.main(["/nonexistent/file.txt"]) == 1
    assert "llmjson:" in capsys.readouterr().err


def test_repair_only_and_find(monkeypatch, capsys):
    code, out, _ = run(["--repair-only"], MESSY, monkeypatch, capsys)
    assert code == 0 and out == '{"a": [1, 2], "b": "x"}\n'
    code, out, _ = run(["--find"], MESSY, monkeypatch, capsys)
    assert code == 0 and out == '{"a": [1, 2,], "b": "x"}\n'


def test_strict(monkeypatch, capsys):
    code, out, err = run(["--strict"], MESSY, monkeypatch, capsys)
    assert code == 1 and out == "" and "could not parse" in err


def test_failure_exit_code(monkeypatch, capsys):
    code, out, err = run([], "no json at all", monkeypatch, capsys)
    assert code == 1 and out == "" and "no JSON" in err


def test_all(monkeypatch, capsys):
    code, out, _ = run(["--all"], 'a {"x": 1} b [2,] c', monkeypatch, capsys)
    assert code == 0 and out == '{"x":1}\n[2]\n'
    code, _, _ = run(["--all"], "nothing", monkeypatch, capsys)
    assert code == 1


def test_ascii_flag(monkeypatch, capsys):
    code, out, _ = run(["-r"], '{"z": "中"}', monkeypatch, capsys)
    assert out == '{"z":"中"}\n'
    code, out, _ = run(["-r", "--ascii"], '{"z": "中"}', monkeypatch, capsys)
    assert out == '{"z":"\\u4e2d"}\n'


def test_python_dash_m():
    r = subprocess.run(
        [sys.executable, "-m", "llmjson", "--raw"], input=MESSY.encode(), capture_output=True, check=False
    )
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"a": [1, 2], "b": "x"}


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0
    assert "llmjson 0.1.0" in capsys.readouterr().out
