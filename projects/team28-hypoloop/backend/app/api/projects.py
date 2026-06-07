import shutil
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.path_utils import (
    ensure_dir,
    get_project_dir,
    get_reports_dir,
    list_project_ids,
)
from app.db.session import init_db, remove_engine

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    project_id: str | None = None  # auto-generated if omitted
    name: str | None = None


class ProjectResponse(BaseModel):
    project_id: str


class ProjectListItem(BaseModel):
    project_id: str
    name: str


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(body: ProjectCreate) -> ProjectResponse:
    """Create a project directory, initialise its SQLite DB, and return the project_id."""
    project_id = body.project_id or str(uuid.uuid4())
    ensure_dir(get_project_dir(project_id))
    ensure_dir(get_reports_dir(project_id))
    init_db(project_id)
    return ProjectResponse(project_id=project_id)


@router.get("", response_model=list[ProjectListItem])
def list_projects() -> list[ProjectListItem]:
    """
    List all initialised projects.

    Note: the data layer has no project-name storage (out of BACKEND_TASK.md scope),
    so the display name is currently the project_id itself; the frontend may show
    its own fixed/overridden label.
    """
    return [ProjectListItem(project_id=pid, name=pid) for pid in list_project_ids()]


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    """Delete a project's directory tree (DB, YMLs, experiments) and drop its cached engine."""
    project_dir = get_project_dir(project_id)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    remove_engine(project_id)
    shutil.rmtree(project_dir)
