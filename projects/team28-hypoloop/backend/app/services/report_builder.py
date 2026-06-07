from typing import Optional

from app.core.path_utils import (
    get_experiment_yml_path,
    get_experiments_dir,
    get_status_yml_path,
)
from app.services.yml_generator import read_experiment_yml, read_status_yml


def _collect_experiment_data(project_id: str, hypothesis_id: str) -> list[dict]:
    """
    Walk the hypothesis's experiments directory and combine, per experiment:
      - status.yml   : current_task / status / last_updated / analysis_text (always present)
      - exp_id.yml   : score (agent-written; may not exist yet, so treated as optional)
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
        status = read_status_yml(status_path) if status_path.exists() else {}

        exp_yml_path = get_experiment_yml_path(project_id, hypothesis_id, exp_id)
        design = read_experiment_yml(exp_yml_path) if exp_yml_path.exists() else {}

        results.append(
            {
                "exp_id": exp_id,
                "status": status.get("status"),
                "current_task": status.get("current_task"),
                "last_updated": status.get("last_updated"),
                "analysis_text": status.get("analysis_text"),
                "score": design.get("score"),
            }
        )
    return results


def get_hypothesis_status(project_id: str, hypothesis_id: str) -> str:
    """
    Derive a coarse hypothesis-level status from its experiments' status.yml files
    (UI display only — the DB stores no status column for hypotheses):
      - "registered": no experiments created yet
      - "error":      at least one experiment failed
      - "done":       experiments exist and all are done
      - "running":    experiments exist but are still in progress
    """
    data = _collect_experiment_data(project_id, hypothesis_id)
    if not data:
        return "registered"
    statuses = [d["status"] for d in data]
    if any(s == "failed" for s in statuses):
        return "error"
    if all(s == "done" for s in statuses):
        return "done"
    return "running"


def get_best_score(project_id: str, hypothesis_id: str) -> Optional[float]:
    """Return the highest score (read from each exp_id.yml), or None if no scores yet."""
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
            "last_updated": d["last_updated"],
        }
        for d in _collect_experiment_data(project_id, hypothesis_id)
    ]


def build_report(project_id: str, hypothesis_id: str) -> dict:
    """
    Aggregate report data for a hypothesis by combining status.yml and exp_id.yml:
      - best_score: highest score across experiments (from exp_id.yml)
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
    }
