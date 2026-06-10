"""세션 보관 + 에이전트 시뮬레이션 MockStore. 순수 Python(Streamlit 비의존)."""
from __future__ import annotations

import os
import tempfile
import threading
import time
import uuid
from typing import Dict, Iterator, List, Tuple

from src.api.types import Project, Hypothesis, AgentEvent
from src.api._sample_charts import make_report_images

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
        # 보고서/이미지를 저장할 데이터 루트(에이전트가 디스크에 저장하는 구조 모사)
        self._data_root = tempfile.mkdtemp(prefix="hypoloop_data_")
        # 시작 시 프로젝트 없음 — 사용자가 [+ 새 프로젝트]로 직접 생성한다.

    def list_projects(self) -> List[Project]:
        return list(self._projects)

    def get_project(self, project_id: str) -> Project:
        for p in self._projects:
            if p.project_id == project_id:
                return p
        raise KeyError(project_id)

    def create_project(self, name: str) -> Project:
        p = Project(project_id=str(uuid.uuid4()), name=name)
        self._projects.append(p)
        return p

    def rename_project(self, project_id: str, name: str) -> Project:
        return self.update_project(project_id, name=name)

    def update_project(self, project_id: str, **fields) -> Project:
        """프로젝트 필드 부분 갱신(name/description/desc_filename/data_csv/data_filename)."""
        p = self.get_project(project_id)
        allowed = {"name", "description", "desc_filename",
                   "train_csv", "train_filename", "test_csv", "test_filename"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(p, k, v)
        return p

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
        try:
            proj = self.get_project(h.project_id)
        except KeyError:
            proj = None
        train_name = (proj.train_filename if proj and proj.train_filename
                      else "train.csv")
        test_name = (proj.test_filename if proj and proj.test_filename
                     else "test.csv")
        desc_snip = ""
        if proj and proj.description:
            desc_snip = proj.description.strip().splitlines()[0][:120]
        data_lines = (
            f"- 학습 데이터: {train_name}\n"
            f"- 실험 데이터: {test_name}\n"
            f"- 설명: {desc_snip or '프로젝트 설명(TXT) 참고'}\n"
            f"- 전처리: 결측치 처리, 범주형 인코딩, 스케일링\n"
        )
        # 에이전트 저장 구조: {가설번호}/img/{이미지}. report_dir = 가설 디렉토리.
        report_dir = os.path.join(self._data_root, "projects", h.project_id,
                                  "hypotheses", h.hypothesis_id)
        images = make_report_images(seed=self._seq)
        eda_section = ""
        if images:
            for rel, raw in images.items():
                fp = os.path.join(report_dir, rel)
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                with open(fp, "wb") as f:
                    f.write(raw)
            eda_section = (
                "## 탐색적 데이터 분석(EDA)\n\n"
                "타깃(SalePrice)은 우편향이 강해 `log1p` 변환으로 정규분포에 가깝게 보정했습니다.\n\n"
                "![Target Distribution](img/target_distribution.png)\n\n"
                "수치형 피처의 왜도를 계산해 왜도가 큰 피처를 확인했습니다.\n\n"
                "![Top Skewed Features](img/skewed_features.png)\n\n"
                "가장 왜도가 큰 피처에 로그 변환을 적용한 효과 예시입니다.\n\n"
                "![Example Feature Transformation](img/example_feature_transformation.png)\n\n"
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
            f"{data_lines}\n"
            f"{eda_section}"
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
        # report.md도 디렉토리에 저장하고 경로를 가설에 기록(프론트가 경로로 병합)
        if images:
            os.makedirs(report_dir, exist_ok=True)
            with open(os.path.join(report_dir, "report.md"), "w",
                      encoding="utf-8") as f:
                f.write(h.report_md)
            h.report_dir = report_dir
        h.status = "done"
        yield AgentEvent("보고서 작성", "log", "보고서 작성 완료")

    def get_report(self, hypothesis_id: str) -> Hypothesis:
        return self._hyps[hypothesis_id]

    def best_scores(self, project_id: str) -> List[Tuple[Hypothesis, float]]:
        return [(h, h.best_score) for h in self.list_hypotheses(project_id)
                if h.status == "done" and h.best_score is not None]
