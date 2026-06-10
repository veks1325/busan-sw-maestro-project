import uuid

from fastapi import APIRouter, HTTPException

from app.core.path_utils import ensure_dir, get_experiment_dir, get_status_yml_path
from app.services import yml_generator

router = APIRouter(tags=["experiments"])


@router.post("/hypotheses/{hypothesis_id}/experiments", status_code=201)
def create_experiment(
    hypothesis_id: str,
    project_id: str,
) -> dict:
    """
    Create an experiment directory and write backend-owned YML skeletons.
    project_id is a required query parameter.
    """
    exp_id = str(uuid.uuid4())
    ensure_dir(get_experiment_dir(project_id, hypothesis_id, exp_id))
    yml_generator.generate_experiment_yml(
        project_id=project_id,
        hypothesis_id=hypothesis_id,
        exp_id=exp_id,
    )
    yml_generator.generate_status_yml(
        project_id=project_id,
        hypothesis_id=hypothesis_id,
        exp_id=exp_id,
    )
    return {"exp_id": exp_id, "hypothesis_id": hypothesis_id, "status": "ready"}


@router.get("/experiments/{exp_id}/status")
def get_experiment_status(
    exp_id: str,
    project_id: str,
    hypothesis_id: str,
) -> dict:
    """
    Read and return the current status.yml for an experiment.
    project_id and hypothesis_id are required query parameters to locate the file.
    """
    status_path = get_status_yml_path(project_id, hypothesis_id, exp_id)
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="Experiment status not found")
    return yml_generator.read_status_yml(status_path)
