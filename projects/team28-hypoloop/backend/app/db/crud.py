from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import DataCard, Hypothesis


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


def create_data_card(
    db: Session,
    *,
    card_id: str,
    project_id: str,
    name: str,
    original_filename: str,
    file_path: str,
    role: Optional[str] = None,
) -> DataCard:
    """Insert a new data card record and return it."""
    row = DataCard(
        card_id=card_id,
        project_id=project_id,
        name=name,
        original_filename=original_filename,
        file_path=file_path,
        role=role,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_data_card(db: Session, card_id: str) -> Optional[DataCard]:
    """Return a data card by ID, or None if not found."""
    return db.get(DataCard, card_id)


def list_data_cards(db: Session, project_id: str) -> list[DataCard]:
    """Return all data cards belonging to a project."""
    return db.query(DataCard).filter(DataCard.project_id == project_id).all()


def delete_data_card(db: Session, card_id: str) -> bool:
    """Delete a data card record by ID. Returns True if a row was removed."""
    row = db.get(DataCard, card_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def get_data_card_by_role(db: Session, project_id: str, role: str) -> Optional[DataCard]:
    """Return the data card with the given role for a project, or None."""
    return (
        db.query(DataCard)
        .filter(DataCard.project_id == project_id, DataCard.role == role)
        .first()
    )


def delete_data_cards_by_role(db: Session, project_id: str, role: str) -> int:
    """Delete all data cards with the given role for a project. Returns count deleted."""
    rows = (
        db.query(DataCard)
        .filter(DataCard.project_id == project_id, DataCard.role == role)
        .all()
    )
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)
