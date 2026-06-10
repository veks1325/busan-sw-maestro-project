from pathlib import Path

import yaml

from app.core import path_utils
from app.services.report_builder import build_report, get_hypothesis_status


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_done_status_without_report_artifacts_is_still_running(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    exp_dir = (
        tmp_path
        / "projects"
        / "project-1"
        / "hypotheses"
        / "hypothesis-1"
        / "experiments"
        / "experiment-1"
    )
    _write_yaml(exp_dir / "status.yml", {"status": "done"})
    _write_yaml(exp_dir / "experiment-1.yml", {"score": None})

    assert get_hypothesis_status("project-1", "hypothesis-1") == "running"


def test_done_status_with_complete_artifacts_is_done(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    exp_dir = (
        tmp_path
        / "projects"
        / "project-1"
        / "hypotheses"
        / "hypothesis-1"
        / "experiments"
        / "experiment-1"
    )
    _write_yaml(exp_dir / "status.yml", {"status": "done"})
    _write_yaml(exp_dir / "experiment-1.yml", {"score": 0.8})
    for filename in ("eda.py", "train.py", "report.md"):
        (exp_dir / filename).write_text("complete", encoding="utf-8")

    assert get_hypothesis_status("project-1", "hypothesis-1") == "done"

    report = build_report("project-1", "hypothesis-1")
    detail = report["experiment_reports"][0]
    assert detail["exp_id"] == "experiment-1"
    assert detail["score"] == 0.8
    assert detail["report_md"] == "complete"
    assert Path(detail["report_dir"]) == exp_dir.resolve()


def test_legacy_fixed_name_experiment_yml_is_supported(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    exp_dir = (
        tmp_path
        / "projects"
        / "project-1"
        / "hypotheses"
        / "hypothesis-1"
        / "experiments"
        / "experiment-1"
    )
    _write_yaml(exp_dir / "status.yml", {"status": "done"})
    _write_yaml(exp_dir / "exp_id.yml", {"score": 0.8})
    for filename in ("eda.py", "train.py", "report.md"):
        (exp_dir / filename).write_text("complete", encoding="utf-8")

    assert get_hypothesis_status("project-1", "hypothesis-1") == "done"


def test_malformed_experiment_yml_does_not_break_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    exp_dir = (
        tmp_path
        / "projects"
        / "project-1"
        / "hypotheses"
        / "hypothesis-1"
        / "experiments"
        / "experiment-1"
    )
    _write_yaml(
        exp_dir / "status.yml",
        {"status": "failed", "analysis_text": "experiment YAML is unreadable"},
    )
    (exp_dir / "experiment-1.yml").write_text(
        "design:\n  experiment_text: invalid value: details\n",
        encoding="utf-8",
    )

    report = build_report("project-1", "hypothesis-1")

    assert report["best_score"] is None
    assert report["score_history"][0]["status"] == "failed"
    assert report["analysis_texts"][0]["text"] == "experiment YAML is unreadable"


def test_report_exposes_current_task_for_live_tracing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    exp_dir = (
        tmp_path
        / "projects"
        / "project-1"
        / "hypotheses"
        / "hypothesis-1"
        / "experiments"
        / "experiment-1"
    )
    _write_yaml(
        exp_dir / "status.yml",
        {
            "status": "running",
            "current_task": "EDA 진행 중",
            "last_updated": "2026-06-10T22:00:00",
        },
    )
    _write_yaml(exp_dir / "experiment-1.yml", {"score": None})

    history = build_report("project-1", "hypothesis-1")["score_history"]

    assert history[0]["current_task"] == "EDA 진행 중"
