from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.path_utils import ensure_dir, get_project_db_path

_engines: dict[str, Engine] = {}


def get_engine(project_id: str) -> Engine:
    """Return a cached SQLAlchemy engine for the given project's SQLite DB."""
    if project_id not in _engines:
        db_path = get_project_db_path(project_id)
        ensure_dir(db_path.parent)
        _engines[project_id] = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
    return _engines[project_id]


def get_db(project_id: str) -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session for the given project."""
    engine = get_engine(project_id)
    from app.db.models import Base

    # Repository samples and older projects may predate the current schema.
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(project_id: str) -> None:
    """Create all tables in the project DB if they do not already exist."""
    from app.db.models import Base  # deferred to avoid circular import

    Base.metadata.create_all(bind=get_engine(project_id))


def remove_engine(project_id: str) -> None:
    """Dispose and remove a cached project engine before deleting its files."""
    engine = _engines.pop(project_id, None)
    if engine is not None:
        engine.dispose()
