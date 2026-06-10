from pathlib import Path
from typing import Callable, Optional

import yaml

from app.core.path_utils import (
    get_experiment_yml_path,
    get_experiments_dir,
    get_legacy_experiment_yml_path,
    get_status_yml_path,
)
from app.services.yml_generator import read_experiment_yml, read_status_yml


def _read_yaml_or_empty(path: Path, reader: Callable[[Path], dict]) -> dict:
    """Return a YAML mapping, isolating missing or malformed agent output."""
    if not path.exists():
        return {}
    try:
        data = reader(path)
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text_or_empty(path: Path) -> str:
    """Read a UTF-8 text artifact without breaking report aggregation."""
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _collect_experiment_data(project_id: str, hypothesis_id: str) -> list[dict]:
    """
    Walk the hypothesis's experiments directory and combine, per experiment:
      - status.yml   : current_task / status / last_updated / analysis_text (always present)
      - <exp_id>.yml : score (agent-written; may not exist yet, so treated as optional)
    Returns one merged dict per experiment, ordered by directory name.
    """
    experiments_dir = get_experiments_dir(project_id, hypothesis_id)
    if not experiments_dir.exists():
        return []

    results = []
    for exp_dir in sorted(experiments_dir.iterdir()):
        if not exp_dir.is_dir():
            continue
        exp_id = exp_dir.name

        status_path = get_status_yml_path(project_id, hypothesis_id, exp_id)
        status = _read_yaml_or_empty(status_path, read_status_yml)

        exp_yml_path = get_experiment_yml_path(project_id, hypothesis_id, exp_id)
        if not exp_yml_path.exists():
            exp_yml_path = get_legacy_experiment_yml_path(
                project_id,
                hypothesis_id,
                exp_id,
            )
        design = _read_yaml_or_empty(exp_yml_path, read_experiment_yml)
        report_md = _read_text_or_empty(exp_dir / "report.md")
        report_exists = bool(report_md)
        artifacts_complete = all(
            (exp_dir / filename).is_file()
            for filename in ("eda.py", "train.py", "report.md")
        )
        score = design.get("score")
        raw_status = status.get("status")
        effective_status = raw_status
        if raw_status == "done" and (
            not artifacts_complete or not isinstance(score, (int, float))
        ):
            effective_status = "running"

        results.append(
            {
                "exp_id": exp_id,
                "status": effective_status,
                "current_task": status.get("current_task"),
                "last_updated": status.get("last_updated"),
                "analysis_text": status.get("analysis_text"),
                "score": score,
                "report_exists": report_exists,
                "report_md": report_md,
                "report_dir": str(exp_dir.resolve()) if report_exists else "",
            }
        )
    return results


def get_hypothesis_status(project_id: str, hypothesis_id: str) -> str:
    """Derive the UI-level hypothesis status from experiment status files."""
    data = _collect_experiment_data(project_id, hypothesis_id)
    if not data:
        return "registered"
    statuses = [item["status"] for item in data]
    if any(status == "failed" for status in statuses):
        return "error"
    if all(status == "done" for status in statuses):
        return "done"
    return "running"


def get_best_score(project_id: str, hypothesis_id: str) -> Optional[float]:
    """Return the highest score from experiment YAML files, or None."""
    data = _collect_experiment_data(project_id, hypothesis_id)
    scores = [d["score"] for d in data if d["score"] is not None]
    return max(scores) if scores else None


def get_score_history(project_id: str, hypothesis_id: str) -> list[dict]:
    """Return per-experiment score/status data ordered by directory name, for graphing."""
    return [
        {
            "exp_id": d["exp_id"],
            "score": d["score"],
            "status": d["status"],
            "current_task": d["current_task"],
            "last_updated": d["last_updated"],
        }
        for d in _collect_experiment_data(project_id, hypothesis_id)
    ]


def build_report(project_id: str, hypothesis_id: str) -> dict:
    """
    Aggregate report data by combining status.yml and <exp_id>.yml:
      - best_score: highest score across experiment YAML files
      - score_history: per-experiment score/status list for graphing
      - analysis_texts: analysis/log text from experiments that have one (from status.yml)
    """
    data = _collect_experiment_data(project_id, hypothesis_id)
    scores = [d["score"] for d in data if d["score"] is not None]
    return {
        "hypothesis_id": hypothesis_id,
        "best_score": max(scores) if scores else None,
        "score_history": [
            {
                "exp_id": d["exp_id"],
                "score": d["score"],
                "status": d["status"],
                "current_task": d["current_task"],
                "last_updated": d["last_updated"],
            }
            for d in data
        ],
        "analysis_texts": [
            {"exp_id": d["exp_id"], "text": d["analysis_text"]}
            for d in data
            if d["analysis_text"] is not None
        ],
        "experiment_reports": [
            {
                "exp_id": d["exp_id"],
                "score": d["score"],
                "status": d["status"],
                "report_md": d["report_md"],
                "report_dir": d["report_dir"],
            }
            for d in data
            if d["report_exists"]
        ],
    }
