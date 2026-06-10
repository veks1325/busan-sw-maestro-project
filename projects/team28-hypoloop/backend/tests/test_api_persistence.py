from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.core import path_utils
from app.db import session
from app.main import app
from app.services import trigger


def test_ready_creates_local_yml_and_data_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(trigger, "_notify_agent", lambda **kwargs: None)
    session._engines.clear()
    client = TestClient(app)

    project = client.post("/projects", json={"name": "test"})
    assert project.status_code == 201
    project_id = project.json()["project_id"]

    upload = client.post(
        f"/projects/{project_id}/data-cards",
        data={"name": "train.csv", "role": "train"},
        files={"file": ("train.csv", b"feature,target\n1,2\n3,4\n", "text/csv")},
    )
    assert upload.status_code == 201

    test_upload = client.post(
        f"/projects/{project_id}/data-cards",
        data={"name": "holdout.csv", "role": "test"},
        files={"file": ("holdout.csv", b"feature\n5\n", "text/csv")},
    )
    assert test_upload.status_code == 201

    description_upload = client.post(
        f"/projects/{project_id}/data-cards",
        data={"name": "description.txt", "role": "description"},
        files={"file": ("description.txt", b"target: prediction target", "text/plain")},
    )
    assert description_upload.status_code == 201

    hypothesis = client.post(
        f"/projects/{project_id}/hypotheses",
        json={
            "u_id": "demo_user",
            "content": "feature affects target",
            "max_experiments": 3,
            "parallel_count": 2,
        },
    )
    assert hypothesis.status_code == 201
    hypothesis_id = hypothesis.json()["hypothesis_id"]

    ready = client.post(
        f"/hypotheses/{hypothesis_id}/ready",
        params={"project_id": project_id, "u_id": "demo_user"},
    )
    assert ready.status_code == 200

    hypothesis_dir = tmp_path / "projects" / project_id / "hypotheses" / hypothesis_id
    hypothesis_yml = hypothesis_dir / f"demo_user_{hypothesis_id}.yml"
    hypothesis_data = yaml.safe_load(hypothesis_yml.read_text(encoding="utf-8"))
    assert hypothesis_data["ready"] is True
    assert "data_card_id" not in hypothesis_data

    project_dir = tmp_path / "projects" / project_id
    assert (project_dir / "train.csv").read_text(encoding="utf-8") == "feature,target\n1,2\n3,4\n"
    assert (project_dir / "test.csv").read_text(encoding="utf-8") == "feature\n5\n"
    assert (project_dir / "data_description.txt").read_text(encoding="utf-8") == "target: prediction target"

    experiment_dirs = sorted((hypothesis_dir / "experiments").iterdir())
    assert len(experiment_dirs) == 3
    assert all((directory / f"{directory.name}.yml").exists() for directory in experiment_dirs)
    assert not any((directory / "exp_id.yml").exists() for directory in experiment_dirs)
    assert all((directory / "status.yml").exists() for directory in experiment_dirs)

    assert (project_dir / "project.db").exists()


def test_legacy_project_directory_gets_database_schema(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    session._engines.clear()
    legacy_dir = tmp_path / "projects" / "example_project"
    legacy_dir.mkdir(parents=True)
    client = TestClient(app)

    response = client.get("/projects/example_project/data-cards")

    assert response.status_code == 200
    assert response.json() == []
    assert (legacy_dir / "project.db").exists()


def test_ready_migrates_fixed_experiment_filename(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(trigger, "_notify_agent", lambda **kwargs: None)
    exp_id = "experiment-1"
    exp_dir = (
        tmp_path
        / "projects"
        / "project-1"
        / "hypotheses"
        / "hypothesis-1"
        / "experiments"
        / exp_id
    )
    exp_dir.mkdir(parents=True)
    legacy_path = exp_dir / "exp_id.yml"
    legacy_path.write_text("score: 0.7\n", encoding="utf-8")

    trigger._prepare_experiments(
        project_id="project-1",
        hypothesis_id="hypothesis-1",
        max_experiments=1,
    )

    assert not legacy_path.exists()
    assert (exp_dir / f"{exp_id}.yml").read_text(encoding="utf-8") == "score: 0.7\n"


def test_reupload_replaces_the_canonical_role_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    session._engines.clear()
    client = TestClient(app)
    project_id = client.post("/projects", json={"name": "test"}).json()["project_id"]

    for content in (b"x\n1\n", b"x\n2\n"):
        response = client.post(
            f"/projects/{project_id}/data-cards",
            data={"name": "source.csv", "role": "train"},
            files={"file": ("source.csv", content, "text/csv")},
        )
        assert response.status_code == 201

    project_dir = tmp_path / "projects" / project_id
    assert (project_dir / "train.csv").read_bytes() == b"x\n2\n"
    assert not list(project_dir.glob("*.csv")) == []
    assert [path.name for path in project_dir.glob("*.csv")] == ["train.csv"]
    cards = client.get(f"/projects/{project_id}/data-cards").json()
    assert len(cards) == 1
    assert cards[0]["file_path"].endswith("/train.csv")


def test_listing_migrates_legacy_uuid_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(path_utils, "DATA_ROOT", tmp_path)
    session._engines.clear()
    client = TestClient(app)
    project_id = client.post("/projects", json={"name": "test"}).json()["project_id"]

    project_dir = tmp_path / "projects" / project_id
    legacy_path = project_dir / "legacy-card.csv"
    legacy_path.write_text("x\n1\n", encoding="utf-8")
    with session.get_engine(project_id).begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO data_cards "
            "(card_id, project_id, name, original_filename, file_path, role, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                "legacy-card",
                project_id,
                "train.csv",
                "train.csv",
                f"projects/{project_id}/legacy-card.csv",
                "train",
            ),
        )

    response = client.get(f"/projects/{project_id}/data-cards")

    assert response.status_code == 200
    assert not legacy_path.exists()
    assert (project_dir / "train.csv").read_text(encoding="utf-8") == "x\n1\n"
    assert response.json()[0]["file_path"].endswith("/train.csv")
