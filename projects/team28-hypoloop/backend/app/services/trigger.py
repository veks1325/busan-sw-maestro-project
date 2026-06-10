import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

from app.core.path_utils import (
    ensure_dir,
    get_experiment_dir,
    get_experiment_yml_path,
    get_experiments_dir,
    get_hypothesis_yml_path,
    get_legacy_experiment_yml_path,
)
from app.services.yml_generator import (
    generate_experiment_yml,
    generate_status_yml,
    read_hypothesis_yml,
    set_hypothesis_ready,
)

logger = logging.getLogger(__name__)


def set_ready(*, project_id: str, u_id: str, hypothesis_id: str) -> Path:
    """
    Set ready=true in the hypothesis YML, then launch the agent runner as a
    background subprocess. Returns the path of the modified YML file.
    Raises FileNotFoundError if the hypothesis YML does not exist yet.
    """
    yml_path = get_hypothesis_yml_path(project_id, u_id, hypothesis_id)
    if not yml_path.exists():
        raise FileNotFoundError(f"Hypothesis YML not found: {yml_path}")

    hypothesis = read_hypothesis_yml(yml_path)
    _prepare_experiments(
        project_id=project_id,
        hypothesis_id=hypothesis_id,
        max_experiments=int(hypothesis["max_experiments"]),
    )
    set_hypothesis_ready(yml_path)
    _notify_agent(project_id=project_id, u_id=u_id, hypothesis_id=hypothesis_id)
    return yml_path


def _prepare_experiments(
    *,
    project_id: str,
    hypothesis_id: str,
    max_experiments: int,
) -> list[str]:
    """Create missing backend-owned experiment and status YML skeletons."""
    experiments_dir = ensure_dir(get_experiments_dir(project_id, hypothesis_id))
    experiment_dirs = sorted(path for path in experiments_dir.iterdir() if path.is_dir())

    for exp_dir in experiment_dirs:
        exp_id = exp_dir.name
        experiment_yml_path = get_experiment_yml_path(
            project_id,
            hypothesis_id,
            exp_id,
        )
        legacy_yml_path = get_legacy_experiment_yml_path(
            project_id,
            hypothesis_id,
            exp_id,
        )
        if not experiment_yml_path.exists() and legacy_yml_path.exists():
            legacy_yml_path.replace(experiment_yml_path)
        elif not experiment_yml_path.exists():
            generate_experiment_yml(
                project_id=project_id,
                hypothesis_id=hypothesis_id,
                exp_id=exp_id,
            )
        if not (exp_dir / "status.yml").exists():
            generate_status_yml(
                project_id=project_id,
                hypothesis_id=hypothesis_id,
                exp_id=exp_id,
            )

    while len(experiment_dirs) < max_experiments:
        exp_id = str(uuid.uuid4())
        ensure_dir(get_experiment_dir(project_id, hypothesis_id, exp_id))
        generate_experiment_yml(
            project_id=project_id,
            hypothesis_id=hypothesis_id,
            exp_id=exp_id,
        )
        generate_status_yml(
            project_id=project_id,
            hypothesis_id=hypothesis_id,
            exp_id=exp_id,
        )
        experiment_dirs.append(get_experiment_dir(project_id, hypothesis_id, exp_id))

    return [path.name for path in experiment_dirs[:max_experiments]]


def _notify_agent(*, project_id: str, u_id: str, hypothesis_id: str) -> None:
    """Launch agent/src/runner.py as a detached background process."""
    runner_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent", "src", "runner.py")
    )
    cwd_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    subprocess.Popen(
        [
            sys.executable, runner_path,
            "--project_id", project_id,
            "--hypothesis_id", hypothesis_id,
            "--u_id", u_id,
        ],
        cwd=cwd_path,
        env=env,
    )
    logger.info(
        "Launched agent runner for hypothesis %s (project=%s)", hypothesis_id, project_id
    )
