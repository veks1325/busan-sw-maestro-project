import shutil
import uuid
from datetime import datetime
from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.path_utils import (
    ensure_dir,
    get_project_dir,
    get_project_meta_path,
    get_reports_dir,
    list_project_ids,
)
from app.db.session import init_db, remove_engine

router = APIRouter(prefix="/projects", tags=["projects"])


# --- helpers ---

def _write_meta(project_id: str, name: str) -> None:
    meta_path = get_project_meta_path(project_id)
    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {"project_id": project_id, "name": name, "created_at": datetime.utcnow().isoformat()},
            f,
            allow_unicode=True,
            sort_keys=False,
        )


def _read_meta(project_id: str) -> dict:
    meta_path = get_project_meta_path(project_id)
    if not meta_path.exists():
        return {"project_id": project_id, "name": project_id}
    with open(meta_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"project_id": project_id, "name": project_id}


# --- schemas ---

class ProjectCreate(BaseModel):
    name: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str


class ProjectPatch(BaseModel):
    name: str


# --- endpoints ---

@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(body: ProjectCreate = ProjectCreate()) -> ProjectResponse:
    """Create a project directory, initialise its SQLite DB, and return the auto-generated UUID."""
    project_id = str(uuid.uuid4())
    ensure_dir(get_project_dir(project_id))
    ensure_dir(get_reports_dir(project_id))
    init_db(project_id)
    name = (body.name or "").strip() or project_id
    _write_meta(project_id, name)
    return ProjectResponse(project_id=project_id, name=name)


@router.get("", response_model=list[ProjectResponse])
def list_projects() -> list[ProjectResponse]:
    """List all initialised projects."""
    result = []
    for pid in list_project_ids():
        meta = _read_meta(pid)
        result.append(ProjectResponse(project_id=pid, name=meta.get("name", pid)))
    return result


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str) -> ProjectResponse:
    """Return a single project's metadata."""
    if not get_project_dir(project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    meta = _read_meta(project_id)
    return ProjectResponse(project_id=project_id, name=meta.get("name", project_id))


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, body: ProjectPatch) -> ProjectResponse:
    """Update a project's name."""
    if not get_project_dir(project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    meta = _read_meta(project_id)
    meta["name"] = body.name
    with open(get_project_meta_path(project_id), "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, sort_keys=False)
    return ProjectResponse(project_id=project_id, name=body.name)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    """Delete a project's directory tree (DB, YMLs, experiments) and drop its cached engine."""
    project_dir = get_project_dir(project_id)
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    remove_engine(project_id)
    shutil.rmtree(project_dir)
