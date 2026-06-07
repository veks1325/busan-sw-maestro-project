import os
import subprocess
import sys
from pathlib import Path

from app.core.path_utils import get_hypothesis_yml_path
from app.services.yml_generator import set_hypothesis_ready


def set_ready(*, project_id: str, u_id: str, hypothesis_id: str) -> Path:
    """
    Set ready=true in the hypothesis YML, then notify the agent.
    Returns the path of the modified YML file.
    Raises FileNotFoundError if the hypothesis YML does not exist yet.
    """
    yml_path = get_hypothesis_yml_path(project_id, u_id, hypothesis_id)
    if not yml_path.exists():
        raise FileNotFoundError(f"Hypothesis YML not found: {yml_path}")

    set_hypothesis_ready(yml_path)

    _notify_agent(project_id=project_id, u_id=u_id, hypothesis_id=hypothesis_id)

    return yml_path


def _notify_agent(*, project_id: str, u_id: str, hypothesis_id: str) -> None:
    """Launch the agent runner script in the background."""
    # This file is at: agn/backend/app/services/trigger.py
    # We want to run: agn/agent/src/runner.py
    runner_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent", "src", "runner.py"))
    cwd_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    # Launch agent as a background subprocess
    subprocess.Popen([
        "python", runner_path,
        "--project_id", project_id,
        "--hypothesis_id", hypothesis_id,
        "--u_id", u_id
    ], cwd=cwd_path, env=env)
