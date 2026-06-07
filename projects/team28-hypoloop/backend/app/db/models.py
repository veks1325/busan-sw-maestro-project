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
