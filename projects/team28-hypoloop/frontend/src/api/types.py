"""프론트 데이터 타입 (feat/backend 계약 미러)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Project:
    project_id: str
    name: str


@dataclass
class Hypothesis:
    hypothesis_id: str
    project_id: str
    content: str
    max_experiments: int          # 최대 실험 길이
    parallel_count: int           # 병렬 횟수
    status: str = "registered"    # "registered" | "running" | "done"
    best_score: Optional[float] = None   # 0~1, 높을수록 좋음
    score_history: List[float] = field(default_factory=list)
    analysis_text: str = ""
    report_md: str = ""
    events: List["AgentEvent"] = field(default_factory=list)  # 라이브 진행 로그


@dataclass
class AgentEvent:
    phase: str                    # 단계명
    kind: str                     # "step" | "tool" | "code" | "log" | "metric"
    text: str
    score: Optional[float] = None  # kind=="metric"일 때 0~1
