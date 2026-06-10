from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    hypothesis_id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    u_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    max_experiments = Column(Integer, nullable=False)
    parallel_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DataCard(Base):
    __tablename__ = "data_cards"

    card_id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # DATA_ROOT 기준 상대경로
    role = Column(String, nullable=True)  # "train" | "test" | "description" | null
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
