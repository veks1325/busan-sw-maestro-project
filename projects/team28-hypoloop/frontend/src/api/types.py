"""프론트 데이터 타입 (feat/backend 계약 미러)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Project:
    project_id: str
    name: str
    train_csv: str = ""          # 학습 데이터(train.csv 텍스트)
    train_filename: str = ""
    test_csv: str = ""           # 실험 데이터(test.csv 텍스트)
    test_filename: str = ""
    description: str = ""         # 데이터 설명(txt 내용)
    desc_filename: str = ""

    @property
    def has_train(self) -> bool:
        return bool(self.train_csv)

    @property
    def has_test(self) -> bool:
        return bool(self.test_csv)

    @property
    def has_desc(self) -> bool:
        return bool(self.description)

    @property
    def is_empty(self) -> bool:
        return not (self.has_train or self.has_test or self.has_desc)

    @property
    def is_ready(self) -> bool:
        """학습(train) + 실험(test) + 설명(txt)이 모두 들어오면 준비 완료."""
        return self.has_train and self.has_test and self.has_desc


@dataclass
class ExperimentReport:
    """One experiment's agent-generated report.md and image base directory."""

    exp_id: str
    status: str
    report_md: str
    report_dir: str
    score: Optional[float] = None


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
    # 보고서(report.md)와 이미지(img/)가 저장된 디렉토리 경로.
    # report_md의 상대경로 이미지(![](img/x.png))를 이 경로 기준으로 프론트가 읽어 병합한다.
    report_dir: str = ""
    experiment_reports: List[ExperimentReport] = field(default_factory=list)
    events: List["AgentEvent"] = field(default_factory=list)  # 라이브 진행 로그


@dataclass
class AgentEvent:
    phase: str                    # 단계명
    kind: str                     # "step" | "tool" | "code" | "log" | "metric"
    text: str
    score: Optional[float] = None  # kind=="metric"일 때 0~1
