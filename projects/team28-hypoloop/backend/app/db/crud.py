from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Hypothesis


def create_hypothesis(
    db: Session,
    *,
    hypothesis_id: str,
    project_id: str,
    u_id: str,
    content: str,
    max_experiments: int,
    parallel_count: int,
) -> Hypothesis:
    """Insert a new hypothesis record and return it."""
    row = Hypothesis(
        hypothesis_id=hypothesis_id,
        project_id=project_id,
        u_id=u_id,
        content=content,
        max_experiments=max_experiments,
        parallel_count=parallel_count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_hypothesis(db: Session, hypothesis_id: str) -> Optional[Hypothesis]:
    """Return a hypothesis by ID, or None if not found."""
    return db.get(Hypothesis, hypothesis_id)


def list_hypotheses(db: Session, project_id: str) -> list[Hypothesis]:
    """Return all hypotheses belonging to a project."""
    return db.query(Hypothesis).filter(Hypothesis.project_id == project_id).all()


def delete_hypothesis(db: Session, hypothesis_id: str) -> bool:
    """Delete a hypothesis record by ID. Returns True if a row was removed."""
    row = db.get(Hypothesis, hypothesis_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
