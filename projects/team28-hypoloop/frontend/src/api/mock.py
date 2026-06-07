"""세션 보관 + 에이전트 시뮬레이션 MockStore. 순수 Python(Streamlit 비의존)."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Dict, Iterator, List, Tuple

from src.api.types import Project, Hypothesis, AgentEvent

PHASES = ["계획 수립", "EDA", "실험 설계", "학습 코드 생성", "학습/평가", "보고서 작성"]
_STEP_DELAY = 1.2   # 실제 에이전트처럼 시간이 걸리도록(백그라운드 실행에서 노란 '동작중' 표시)


class MockStore:
    """HypoStore 구현(데모용). 가설을 메모리에 보관하고 run()을 시뮬레이션한다."""

    def __init__(self, step_delay: float = _STEP_DELAY) -> None:
        self._step_delay = step_delay
        self._projects: List[Project] = []
        self._hyps: Dict[str, Hypothesis] = {}   # 삽입 순서 = 생성 순서
        self._base: Dict[str, float] = {}
        self._seq = 0
        self._threads: Dict[str, threading.Thread] = {}   # 백그라운드 실행
        # 기본 프로젝트 1개 (이후 create_project로 추가)
        self.create_project("타이타닉 생존 예측")

    def list_projects(self) -> List[Project]:
        return list(self._projects)

    def create_project(self, name: str) -> Project:
        p = Project(project_id=str(uuid.uuid4()), name=name)
        self._projects.append(p)
        return p

    def rename_project(self, project_id: str, name: str) -> Project:
        for p in self._projects:
            if p.project_id == project_id:
                p.name = name
                return p
        raise KeyError(project_id)

    def delete_project(self, project_id: str) -> None:
        self._projects = [p for p in self._projects
                          if p.project_id != project_id]
        for hid in [h.hypothesis_id for h in self._hyps.values()
                    if h.project_id == project_id]:
            self._hyps.pop(hid, None)
            self._base.pop(hid, None)

    def list_hypotheses(self, project_id: str) -> List[Hypothesis]:
        return [h for h in self._hyps.values() if h.project_id == project_id]

    def create_hypothesis(self, project_id: str, content: str,
                          max_experiments: int, parallel_count: int) -> Hypothesis:
        hid = str(uuid.uuid4())
        h = Hypothesis(hypothesis_id=hid, project_id=project_id,
                       content=content, max_experiments=max_experiments,
                       parallel_count=parallel_count)
        self._hyps[hid] = h
        self._base[hid] = 0.55 + 0.07 * (self._seq % 5)
        self._seq += 1
        return h

    def delete_hypothesis(self, hypothesis_id: str) -> None:
        self._hyps.pop(hypothesis_id, None)
        self._base.pop(hypothesis_id, None)

    def start_run(self, hypothesis_id: str) -> None:
        """백그라운드 스레드로 실행을 시작하고 즉시 반환(논블로킹).

        실제 에이전트 백엔드의 'ready/trigger 후 폴링' 흐름을 모사한다.
        UI는 차단되지 않으며 h.status/score_history/events가 시간에 따라 갱신된다.
        """
        h = self._hyps[hypothesis_id]
        h.status = "running"          # 즉시 '동작중'(노란색)으로 표시
        h.score_history = []
        h.events = []
        prev = self._threads.get(hypothesis_id)
        if prev is not None and prev.is_alive():
            return
        t = threading.Thread(target=self._drain, args=(hypothesis_id,),
                             daemon=True)
        self._threads[hypothesis_id] = t
        t.start()

    def _drain(self, hypothesis_id: str) -> None:
        """run() 제너레이터를 소비하며 이벤트를 가설에 누적(백그라운드 전용)."""
        try:
            for ev in self.run(hypothesis_id):
                h = self._hyps.get(hypothesis_id)
                if h is None:         # 실행 중 삭제됨
                    return
                h.events.append(ev)
        except KeyError:
            return                    # 실행 중 삭제됨

    def run(self, hypothesis_id: str) -> Iterator[AgentEvent]:
        h = self._hyps[hypothesis_id]
        h.status = "running"
        h.score_history = []
        base = self._base[hypothesis_id]

        yield AgentEvent("계획 수립", "step", "가설을 분석하고 실험 계획을 수립하는 중")
        yield AgentEvent("계획 수립", "tool", "프로젝트 데이터 스키마 조회(SQLite)")
        time.sleep(self._step_delay)
        yield AgentEvent("EDA", "step", "탐색적 데이터 분석 수행 중")
        yield AgentEvent("EDA", "code", "import pandas as pd\ndf.describe()")
        time.sleep(self._step_delay)

        for i in range(1, h.max_experiments + 1):
            yield AgentEvent("실험 설계", "step",
                             f"실험 {i}/{h.max_experiments} 설계 중")
            yield AgentEvent("실험 설계", "tool",
                             "Solar API로 피처·하이퍼파라미터 제안")
            yield AgentEvent("학습 코드 생성", "code",
                             f"# 실험 {i} 학습 코드\nmodel.fit(X_train, y_train)")
            yield AgentEvent("학습/평가", "step", f"실험 {i} 학습·평가 중")
            time.sleep(self._step_delay)
            score = round(min(base + 0.04 * i, 0.97), 4)
            h.score_history.append(score)
            yield AgentEvent("학습/평가", "metric",
                             f"실험 {i} 점수 {score}", score=score)

        yield AgentEvent("보고서 작성", "step", "결과를 종합해 보고서 작성 중")
        time.sleep(self._step_delay)
        h.best_score = max(h.score_history)
        best_i = h.score_history.index(h.best_score) + 1
        h.analysis_text = (
            f"총 {h.max_experiments}회 실험에서 최고 점수 {h.best_score}를 달성했습니다. "
            f"실험을 거듭할수록 점수가 향상되는 경향을 보였습니다."
        )
        rows = "\n".join(
            f"| {i} | {s} |" + ("  ← 최고" if i == best_i else "")
            for i, s in enumerate(h.score_history, start=1)
        )
        h.report_md = (
            f"# 분석 보고서\n\n"
            f"이 보고서는 에이전트가 자동 생성한 실험 결과 요약입니다. "
            f"좌측 목차로 섹션을 이동할 수 있고, 하단 바에서 읽은 비율을 확인할 수 있습니다.\n\n"
            f"## 개요\n\n"
            f"본 실험은 아래 가설을 검증하기 위해 총 {h.max_experiments}회의 반복 실험"
            f"(병렬 {h.parallel_count})을 수행했습니다. 각 반복마다 피처 구성과 "
            f"하이퍼파라미터를 조정하며 평가 점수(0~1)를 측정했습니다.\n\n"
            f"## 가설\n\n> {h.content}\n\n"
            f"## 데이터 개요\n\n"
            f"- 소스: 프로젝트 로컬 DB(SQLite)\n"
            f"- 전처리: 결측치 처리, 범주형 인코딩, 표준화\n"
            f"- 분할: 학습/검증 = 80/20\n\n"
            f"## 실험 설정\n\n"
            f"- 최대 실험 횟수: {h.max_experiments}\n"
            f"- 병렬 횟수: {h.parallel_count}\n"
            f"- 평가 지표: 0~1 점수(높을수록 좋음)\n\n"
            f"## 실험별 결과\n\n"
            f"| 실험 | 점수 |\n| --- | --- |\n{rows}\n\n"
            f"## 성능 요약\n\n"
            f"- 최고 점수: **{h.best_score}** (실험 {best_i})\n"
            f"- 평균 점수: **{round(sum(h.score_history)/len(h.score_history), 4)}**\n"
            f"- 추세: 반복이 진행될수록 점수가 향상\n\n"
            f"## 결과 분석\n\n{h.analysis_text} "
            f"피처 중요도 분석 결과 상위 피처가 예측에 크게 기여했으며, "
            f"하이퍼파라미터 조정으로 과적합을 완화할 수 있었습니다.\n\n"
            f"## 결론 및 향후 과제\n\n"
            f"가설은 데이터상 유의미하게 지지되었습니다. 향후에는 더 다양한 피처 조합과 "
            f"교차검증을 통해 일반화 성능을 추가로 검증할 필요가 있습니다.\n"
        )
        h.status = "done"
        yield AgentEvent("보고서 작성", "log", "보고서 작성 완료")

    def get_report(self, hypothesis_id: str) -> Hypothesis:
        return self._hyps[hypothesis_id]

    def best_scores(self, project_id: str) -> List[Tuple[Hypothesis, float]]:
        return [(h, h.best_score) for h in self.list_hypotheses(project_id)
                if h.status == "done" and h.best_score is not None]
