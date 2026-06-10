import yaml

from agent.src.tool import (
    MAX_TOOL_OUTPUT_CHARS,
    PROJECT_ROOT,
    execute_command,
    read_file,
    update_status,
    write_file,
)


def test_write_file_normalizes_fully_escaped_python_newlines(tmp_path) -> None:
    target = tmp_path / "generated.py"

    result = write_file.invoke(
        {
            "file_path": str(target),
            "content": "import pandas as pd\\nprint(pd.__name__)",
        }
    )

    assert result.startswith("Successfully wrote")
    assert target.read_text(encoding="utf-8") == "import pandas as pd\nprint(pd.__name__)"


def test_write_file_repairs_escaped_quotes_when_repaired_python_is_valid(tmp_path) -> None:
    target = tmp_path / "generated.py"

    result = write_file.invoke(
        {
            "file_path": str(target),
            "content": 'raise ValueError(f\\"bad value: {1}\\")',
        }
    )

    assert result.startswith("Successfully wrote")
    assert target.read_text(encoding="utf-8") == 'raise ValueError(f"bad value: {1}")'


def test_write_file_reports_unrepaired_python_syntax(tmp_path) -> None:
    target = tmp_path / "generated.py"

    result = write_file.invoke(
        {"file_path": str(target), "content": "if True print('bad')"}
    )

    assert "Python syntax is invalid" in result


def test_read_file_refuses_csv_payloads(tmp_path) -> None:
    target = tmp_path / "large.csv"
    target.write_text("value\n" + "1\n" * 100, encoding="utf-8")

    result = read_file.invoke({"file_path": str(target)})

    assert "not returned through read_file" in result
    assert "pandas summary" in result


def test_read_file_truncates_large_text(tmp_path) -> None:
    target = tmp_path / "description.txt"
    target.write_text("x" * (MAX_TOOL_OUTPUT_CHARS + 500), encoding="utf-8")

    result = read_file.invoke({"file_path": str(target)})

    assert len(result) < MAX_TOOL_OUTPUT_CHARS + 100
    assert "truncated 500 characters" in result


def test_execute_command_truncates_large_output() -> None:
    result = execute_command.invoke(
        {"command": f"python -c \"print('x' * {MAX_TOOL_OUTPUT_CHARS + 500})\""}
    )

    assert "truncated" in result


def test_read_file_resolves_repository_relative_path() -> None:
    result = read_file.invoke({"file_path": "shared/templates/path_rules.md"})

    assert "Agent Path and Authorization Rules" in result


def test_read_file_recovers_shared_path_prefixed_by_hypothesis_dir() -> None:
    wrong_path = (
        PROJECT_ROOT
        / "data/projects/project-1/hypotheses/hypothesis-1"
        / "shared/templates/path_rules.md"
    )

    result = read_file.invoke({"file_path": str(wrong_path)})

    assert "Agent Path and Authorization Rules" in result
    assert len(result) < MAX_TOOL_OUTPUT_CHARS + 100


def test_update_status_rejects_done_before_final_artifacts(tmp_path) -> None:
    (tmp_path / "status.yml").write_text(
        yaml.safe_dump({"status": "running"}), encoding="utf-8"
    )
    (tmp_path / f"{tmp_path.name}.yml").write_text(
        yaml.safe_dump({"score": None}), encoding="utf-8"
    )

    result = update_status.invoke(
        {
            "exp_dir": str(tmp_path),
            "current_task": "설계 완료",
            "status": "done",
        }
    )

    assert result.startswith("Cannot set status to done")
    status = yaml.safe_load((tmp_path / "status.yml").read_text(encoding="utf-8"))
    assert status["status"] == "running"


def test_update_status_allows_done_after_final_artifacts(tmp_path) -> None:
    for filename in ("eda.py", "train.py", "report.md"):
        (tmp_path / filename).write_text("complete", encoding="utf-8")
    (tmp_path / "status.yml").write_text(
        yaml.safe_dump({"status": "running"}), encoding="utf-8"
    )
    (tmp_path / f"{tmp_path.name}.yml").write_text(
        yaml.safe_dump({"score": 0.8}), encoding="utf-8"
    )

    result = update_status.invoke(
        {
            "exp_dir": str(tmp_path),
            "current_task": "실험 완료",
            "status": "done",
        }
    )

    assert result.startswith("Status successfully updated to: done")
