import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                 # hypoloop/
DATA_ROOT = Path(os.getenv("HYPOLOOP_DATA_ROOT", str(_PROJECT_ROOT / "data")))


def get_project_dir(project_id: str) -> Path:
    """Return the root directory for a project."""
    return DATA_ROOT / "projects" / project_id


def get_project_meta_path(project_id: str) -> Path:
    """Return the path for the project meta YAML file (name, created_at)."""
    return get_project_dir(project_id) / "meta.yml"


def get_project_db_path(project_id: str) -> Path:
    """Return the SQLite DB file path for a project."""
    return get_project_dir(project_id) / "project.db"


def get_hypothesis_dir(project_id: str, hypothesis_id: str) -> Path:
    """Return the directory for a hypothesis."""
    return get_project_dir(project_id) / "hypotheses" / hypothesis_id


def get_hypothesis_yml_path(project_id: str, u_id: str, hypothesis_id: str) -> Path:
    """Return the path for the hypothesis YML file (u_id_hypothesis_id.yml)."""
    return get_hypothesis_dir(project_id, hypothesis_id) / f"{u_id}_{hypothesis_id}.yml"


def get_experiment_dir(project_id: str, hypothesis_id: str, exp_id: str) -> Path:
    """Return the directory for an experiment."""
    return get_hypothesis_dir(project_id, hypothesis_id) / "experiments" / exp_id


def get_experiment_yml_path(project_id: str, hypothesis_id: str, exp_id: str) -> Path:
    """Return the canonical experiment YAML path."""
    return get_experiment_dir(project_id, hypothesis_id, exp_id) / f"{exp_id}.yml"


def get_legacy_experiment_yml_path(
    project_id: str,
    hypothesis_id: str,
    exp_id: str,
) -> Path:
    """Return the legacy fixed-name experiment YAML path."""
    return get_experiment_dir(project_id, hypothesis_id, exp_id) / "exp_id.yml"


def get_status_yml_path(project_id: str, hypothesis_id: str, exp_id: str) -> Path:
    """Return the status.yml path inside an experiment directory."""
    return get_experiment_dir(project_id, hypothesis_id, exp_id) / "status.yml"


def get_experiments_dir(project_id: str, hypothesis_id: str) -> Path:
    """Return the experiments directory for a hypothesis."""
    return get_hypothesis_dir(project_id, hypothesis_id) / "experiments"


def get_reports_dir(project_id: str) -> Path:
    """Return the reports directory for a project."""
    return get_project_dir(project_id) / "reports"


def get_project_data_file_path(project_id: str, role: str) -> Path:
    """Return the single canonical file path for a project data role."""
    filenames = {
        "train": "train.csv",
        "test": "test.csv",
        "description": "data_description.txt",
    }
    try:
        filename = filenames[role]
    except KeyError as exc:
        raise ValueError(f"Unsupported data role: {role}") from exc
    return get_project_dir(project_id) / filename


def ensure_dir(path: Path) -> Path:
    """Create the directory (and parents) if it does not exist. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_project_ids() -> list[str]:
    """Return project directory names in stable order."""
    projects_dir = DATA_ROOT / "projects"
    if not projects_dir.exists():
        return []
    return sorted(path.name for path in projects_dir.iterdir() if path.is_dir())
