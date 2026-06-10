from datetime import datetime
from pathlib import Path

import yaml

from app.core.path_utils import (
    ensure_dir,
    get_experiment_yml_path,
    get_hypothesis_yml_path,
    get_status_yml_path,
)


def generate_hypothesis_yml(
    *,
    u_id: str,
    project_id: str,
    hypothesis_id: str,
    content: str,
    max_experiments: int,
    parallel_count: int,
) -> Path:
    """
    Write the hypothesis YML file (u_id_hypothesis_id.yml) to the hypothesis directory.
    Sets ready=false; call set_hypothesis_ready() after triggering.
    Returns the path of the written file.
    """
    data = {
        "u_id": u_id,
        "project_id": project_id,
        "hypothesis_id": hypothesis_id,
        "content": content,
        "max_experiments": max_experiments,
        "parallel_count": parallel_count,
        "ready": False,
    }
    yml_path = get_hypothesis_yml_path(project_id, u_id, hypothesis_id)
    ensure_dir(yml_path.parent)
    _write_yml(yml_path, data)
    return yml_path


def generate_status_yml(
    *,
    project_id: str,
    hypothesis_id: str,
    exp_id: str,
) -> Path:
    """
    Write the initial status.yml for a new experiment (status=ready).
    This file tracks the agent's current task/progress for UI display only —
    the final score and design live in <exp_id>.yml (agent-written).
    Returns the path of the written file.
    """
    data = {
        "hypothesis_id": hypothesis_id,
        "exp_id": exp_id,
        "current_task": None,
        "status": "ready",
        "last_updated": datetime.utcnow().isoformat(),
        "analysis_text": None,
    }
    status_path = get_status_yml_path(project_id, hypothesis_id, exp_id)
    _write_yml(status_path, data)
    return status_path


def generate_experiment_yml(
    *,
    project_id: str,
    hypothesis_id: str,
    exp_id: str,
) -> Path:
    """
    새로운 실험을 위한 초기 <exp_id>.yml 스켈레톤(뼈대) 파일을 생성합니다.
    백엔드는 실험 ID 식별자만 채워넣고, 에이전트가 실험 종료 후 design과 score를 채워넣게 됩니다.
    """
    data = {
        "hypothesis_id": hypothesis_id,
        "exp_id": exp_id,
        "design": {
            "experiment_text": None,
            "model": None,
            "features": [],
            "hyperparameters": {},
            # 데모 시연 및 에이전트 평가 통일성을 위해 평가 산식을 "R2 Score"로 고정 주입합니다.
            "formula": "R2 Score",
        },
        "score": None,
    }
    exp_yml_path = get_experiment_yml_path(project_id, hypothesis_id, exp_id)
    _write_yml(exp_yml_path, data)
    return exp_yml_path


def set_hypothesis_ready(yml_path: Path) -> None:
    """Flip ready=true in an existing hypothesis YML file."""
    data = read_hypothesis_yml(yml_path)
    data["ready"] = True
    _write_yml(yml_path, data)


def read_hypothesis_yml(yml_path: Path) -> dict:
    """Read and return the contents of a hypothesis YML file."""
    with open(yml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_status_yml(status_path: Path) -> dict:
    """Read and return the contents of a status.yml file."""
    with open(status_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_experiment_yml(yml_path: Path) -> dict:
    """Read and return an agent-generated experiment YAML file."""
    with open(yml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write_yml(path: Path, data: dict) -> None:
    """Overwrite a YML file with the given data dict."""
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
