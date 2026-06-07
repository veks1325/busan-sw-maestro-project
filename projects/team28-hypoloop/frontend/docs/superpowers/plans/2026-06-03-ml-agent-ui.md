# ML 자동화 에이전트 UI/프론트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ML 파이프라인 자동화 에이전트의 Streamlit 프론트엔드(입력 폼 + 보고서 뷰어)를 백엔드 계약+Mock 기반으로 독립 완성한다.

**Architecture:** UI는 `PipelineBackend` 추상 인터페이스에만 의존한다. 지금은 `Mock` 구현으로 전체 흐름을 동작·테스트하고, 나중에 Mock을 실제 백엔드로 교체한다. 화면은 세션 상태(`input`→`running`→`report`)로 전환되는 단일 Streamlit 앱이다.

**Tech Stack:** Python 3.10, Streamlit, pandas, PyYAML, pytest

참고 스펙: `docs/superpowers/specs/2026-06-03-ml-agent-ui-design.md`

---

## 파일 구조

```
app.py                      # Streamlit 진입점 + 화면 라우팅
ui/__init__.py
ui/theme.py                 # 스텝 헤더, 카드, 색상 토큰, 경계 문구
ui/input_form.py            # 입력 폼 + 검증 호출
ui/progress_view.py         # 진행 상태 실시간 표시
ui/report_viewer.py         # 보고서 뷰어(4탭) + 다운로드
backend/__init__.py
backend/interface.py        # ★ dataclass 계약 + PipelineBackend Protocol
backend/mock.py             # Mock 구현
sample_data/sample.csv
sample_data/sample_report.md
tests/test_interface.py
tests/test_mock.py
tests/test_input_form.py
requirements.txt
README.md
```

각 파일은 하나의 책임만 진다. `interface.py`가 백엔드 팀과의 유일한 합의 지점이다.

---

## Task 1: 프로젝트 골격

**Files:**
- Create: `requirements.txt`
- Create: `backend/__init__.py`, `ui/__init__.py` (빈 파일)
- Create: `tests/__init__.py` (빈 파일)

- [ ] **Step 1: requirements.txt 작성**

```
streamlit>=1.30
pandas>=2.0
PyYAML>=6.0
pytest>=7.4
```

- [ ] **Step 2: 빈 패키지 파일 생성**

```bash
mkdir -p ui backend tests sample_data
touch ui/__init__.py backend/__init__.py tests/__init__.py
```

- [ ] **Step 3: 의존성 설치 확인**

Run: `pip install -r requirements.txt`
Expected: streamlit/pandas/pyyaml/pytest 설치 성공(이미 설치됐으면 "already satisfied")

- [ ] **Step 4: Commit**

```bash
git add requirements.txt ui/__init__.py backend/__init__.py tests/__init__.py
git commit -m "chore: project skeleton and dependencies"
```

---

## Task 2: 데이터 계약 (interface.py)

**Files:**
- Create: `backend/interface.py`
- Test: `tests/test_interface.py`

- [ ] **Step 1: 계약 테스트 작성**

`tests/test_interface.py`:

```python
from backend.interface import (
    DataCard, PipelineInput, ProgressEvent, MetricRecord,
    PipelineResult, PIPELINE_STAGES,
)


def test_datacard_fields():
    card = DataCard(target_column="Survived", task_type="classification",
                    description="타이타닉")
    assert card.target_column == "Survived"
    assert card.task_type == "classification"


def test_pipeline_input_fields():
    card = DataCard(target_column="y", task_type="regression", description="d")
    inp = PipelineInput(csv_path="/tmp/a.csv", loop_count=3,
                        data_card=card, llm_instruction="가설")
    assert inp.loop_count == 3
    assert inp.data_card.target_column == "y"


def test_progress_event_fields():
    ev = ProgressEvent(stage="EDA", loop_index=0, status="running", message="시작")
    assert ev.stage == "EDA"
    assert ev.status == "running"


def test_metric_record_delta():
    m = MetricRecord(loop_index=1, metric_name="accuracy", baseline=0.7, value=0.82)
    assert round(m.value - m.baseline, 2) == 0.12


def test_pipeline_result_fields():
    res = PipelineResult(report_md="# r", final_code="print(1)",
                         metrics_history=[], experiment_yaml="a: 1")
    assert res.report_md == "# r"
    assert res.metrics_history == []


def test_pipeline_stages_order():
    assert PIPELINE_STAGES[0] == "계획수립"
    assert "베이스라인" in PIPELINE_STAGES
    assert PIPELINE_STAGES[-1] == "리포트"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_interface.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.interface'`

- [ ] **Step 3: interface.py 구현**

`backend/interface.py`:

```python
"""UI ↔ 백엔드 합의 계약. 백엔드 팀은 PipelineBackend를 구현한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Protocol, runtime_checkable

# 파이프라인 단계(진행 화면 체크리스트 순서)
PIPELINE_STAGES: List[str] = [
    "계획수립", "EDA", "베이스라인", "피처엔지니어링", "튜닝", "리포트",
]

# 태스크 종류
TASK_TYPES: List[str] = ["classification", "regression"]


@dataclass
class DataCard:
    target_column: str            # 예측 대상 컬럼
    task_type: str                # "classification" | "regression"
    description: str = ""         # 데이터셋 자유 설명


@dataclass
class PipelineInput:
    csv_path: str                 # 업로드된 CSV 저장 경로
    loop_count: int               # 성능 개선 루프 횟수
    data_card: DataCard
    llm_instruction: str          # 가설·목표·평가산식 자유 텍스트


@dataclass
class ProgressEvent:
    stage: str                    # PIPELINE_STAGES 중 하나
    loop_index: int               # 0 = 베이스라인
    status: str                   # "running" | "done" | "failed"
    message: str                  # 사용자에게 보일 한 줄 설명


@dataclass
class MetricRecord:
    loop_index: int
    metric_name: str              # 예: "accuracy", "rmse"
    baseline: float               # 베이스라인 값
    value: float                  # 해당 루프 값


@dataclass
class PipelineResult:
    report_md: str                # 최종 마크다운 보고서
    final_code: str               # 실행 가능한 Python 코드
    metrics_history: List[MetricRecord] = field(default_factory=list)
    experiment_yaml: str = ""     # 백엔드가 생성한 yml 내용


@runtime_checkable
class PipelineBackend(Protocol):
    """백엔드 구현이 따라야 할 인터페이스."""

    def validate_input(self, inp: PipelineInput) -> List[str]:
        """입력 검증. 문제 메시지 리스트 반환(빈 리스트면 통과)."""
        ...

    def run(self, inp: PipelineInput) -> Iterator[ProgressEvent]:
        """파이프라인 실행. 진행 이벤트를 순차 yield."""
        ...

    def get_result(self) -> PipelineResult:
        """run() 완료 후 최종 결과 반환."""
        ...
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_interface.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/interface.py tests/test_interface.py
git commit -m "feat: define UI-backend data contract (interface.py)"
```

---

## Task 3: Mock 백엔드 (mock.py)

**Files:**
- Create: `backend/mock.py`
- Test: `tests/test_mock.py`

- [ ] **Step 1: Mock 테스트 작성**

`tests/test_mock.py`:

```python
import os
import tempfile

import pandas as pd
import pytest

from backend.interface import (
    DataCard, PipelineInput, PipelineBackend, PIPELINE_STAGES,
)
from backend.mock import MockBackend


@pytest.fixture
def csv_path():
    df = pd.DataFrame({"Pclass": [1, 3, 2], "Survived": [1, 0, 1]})
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    df.to_csv(path, index=False)
    yield path
    os.remove(path)


def make_input(csv_path, loop_count=2, target="Survived"):
    card = DataCard(target_column=target, task_type="classification",
                    description="테스트")
    return PipelineInput(csv_path=csv_path, loop_count=loop_count,
                         data_card=card, llm_instruction="가설 검증")


def test_mock_satisfies_protocol():
    assert isinstance(MockBackend(), PipelineBackend)


def test_validate_ok(csv_path):
    errors = MockBackend().validate_input(make_input(csv_path))
    assert errors == []


def test_validate_missing_target(csv_path):
    errors = MockBackend().validate_input(make_input(csv_path, target="없는컬럼"))
    assert len(errors) == 1
    assert "없는컬럼" in errors[0]


def test_validate_bad_loop_count(csv_path):
    errors = MockBackend().validate_input(make_input(csv_path, loop_count=0))
    assert any("루프" in e for e in errors)


def test_run_streams_events_in_stage_order(csv_path):
    backend = MockBackend()
    events = list(backend.run(make_input(csv_path, loop_count=2)))
    assert len(events) > 0
    seen_stages = [e.stage for e in events]
    # 모든 단계가 등장
    for stage in PIPELINE_STAGES:
        assert stage in seen_stages
    # 마지막 이벤트는 완료 상태
    assert events[-1].status == "done"


def test_get_result_after_run(csv_path):
    backend = MockBackend()
    list(backend.run(make_input(csv_path, loop_count=3)))
    res = backend.get_result()
    assert res.report_md.startswith("#")
    assert "def " in res.final_code or "import" in res.final_code
    assert len(res.metrics_history) >= 1
    # 루프 수만큼 지표 기록(베이스라인 제외 최소 1개)
    assert res.experiment_yaml != ""


def test_get_result_before_run_raises():
    with pytest.raises(RuntimeError):
        MockBackend().get_result()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_mock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.mock'`

- [ ] **Step 3: mock.py 구현**

`backend/mock.py`:

```python
"""백엔드 미완성 동안 UI를 완성·테스트하기 위한 가짜 구현."""
from __future__ import annotations

import time
from typing import Iterator, List, Optional

import pandas as pd

from backend.interface import (
    PipelineInput, ProgressEvent, MetricRecord, PipelineResult,
    PIPELINE_STAGES, TASK_TYPES,
)

# 진행 이벤트 사이 지연(초). 테스트 빠르게 하려고 짧게.
_STEP_DELAY = 0.05


class MockBackend:
    """PipelineBackend 계약을 따르는 가짜 백엔드."""

    def __init__(self, step_delay: float = _STEP_DELAY) -> None:
        self._step_delay = step_delay
        self._result: Optional[PipelineResult] = None

    def validate_input(self, inp: PipelineInput) -> List[str]:
        errors: List[str] = []
        try:
            columns = list(pd.read_csv(inp.csv_path, nrows=1).columns)
        except Exception as exc:  # noqa: BLE001 - 사용자에게 그대로 안내
            return [f"CSV를 읽을 수 없습니다: {exc}"]

        if inp.data_card.target_column not in columns:
            errors.append(
                f"타깃 컬럼 '{inp.data_card.target_column}'이(가) CSV에 없습니다."
            )
        if inp.data_card.task_type not in TASK_TYPES:
            errors.append(f"태스크 종류가 올바르지 않습니다: {inp.data_card.task_type}")
        if inp.loop_count < 1:
            errors.append("루프 횟수는 1 이상이어야 합니다.")
        if not inp.llm_instruction.strip():
            errors.append("언어모델 입력(가설/목표)을 작성해주세요.")
        return errors

    def run(self, inp: PipelineInput) -> Iterator[ProgressEvent]:
        is_clf = inp.data_card.task_type == "classification"
        metric_name = "accuracy" if is_clf else "rmse"
        baseline = 0.70 if is_clf else 0.50
        metrics: List[MetricRecord] = []

        # 베이스라인까지 단계 진행(loop 0)
        for stage in PIPELINE_STAGES[:3]:  # 계획수립, EDA, 베이스라인
            yield ProgressEvent(stage=stage, loop_index=0, status="running",
                                message=f"{stage} 진행 중...")
            time.sleep(self._step_delay)
            yield ProgressEvent(stage=stage, loop_index=0, status="done",
                                message=f"{stage} 완료")
        metrics.append(MetricRecord(loop_index=0, metric_name=metric_name,
                                    baseline=baseline, value=baseline))

        # 개선 루프
        for loop in range(1, inp.loop_count + 1):
            for stage in PIPELINE_STAGES[3:5]:  # 피처엔지니어링, 튜닝
                yield ProgressEvent(stage=stage, loop_index=loop, status="running",
                                    message=f"루프 {loop}: {stage} 진행 중...")
                time.sleep(self._step_delay)
                yield ProgressEvent(stage=stage, loop_index=loop, status="done",
                                    message=f"루프 {loop}: {stage} 완료")
            # 매 루프 가짜 개선(분류는 증가, 회귀는 감소)
            if is_clf:
                value = min(baseline + 0.04 * loop, 0.95)
            else:
                value = max(baseline - 0.03 * loop, 0.10)
            metrics.append(MetricRecord(loop_index=loop, metric_name=metric_name,
                                        baseline=baseline, value=round(value, 4)))

        # 리포트 단계
        yield ProgressEvent(stage="리포트", loop_index=inp.loop_count,
                            status="running", message="리포트 생성 중...")
        time.sleep(self._step_delay)

        self._result = self._build_result(inp, metrics, metric_name)
        yield ProgressEvent(stage="리포트", loop_index=inp.loop_count,
                            status="done", message="완료")

    def get_result(self) -> PipelineResult:
        if self._result is None:
            raise RuntimeError("run()을 먼저 실행해야 결과를 얻을 수 있습니다.")
        return self._result

    def _build_result(self, inp: PipelineInput, metrics: List[MetricRecord],
                      metric_name: str) -> PipelineResult:
        base = metrics[0].value
        best = metrics[-1].value
        delta = round(best - base, 4)
        report_md = (
            f"# 분석 리포트 (Mock)\n\n"
            f"- 데이터: `{inp.csv_path}`\n"
            f"- 타깃: **{inp.data_card.target_column}** "
            f"({inp.data_card.task_type})\n"
            f"- 루프 횟수: {inp.loop_count}\n\n"
            f"## 성능 요약\n\n"
            f"| 구분 | {metric_name} |\n|---|---|\n"
            f"| 베이스라인 | {base} |\n| 최종 | {best} |\n"
            f"| 향상폭(Δ) | {delta} |\n\n"
            f"## 사용자 가설\n\n> {inp.llm_instruction}\n\n"
            f"> ⚠️ 제한된 데이터·환경에서 도출된 결과이므로, "
            f"프로덕션 적용 전 반드시 검토가 필요합니다.\n"
        )
        final_code = (
            "import pandas as pd\n"
            "from sklearn.ensemble import RandomForestClassifier\n\n"
            f"df = pd.read_csv(r'{inp.csv_path}')\n"
            f"y = df['{inp.data_card.target_column}']\n"
            f"X = df.drop(columns=['{inp.data_card.target_column}'])\n"
            "model = RandomForestClassifier().fit(X, y)\n"
            "print('done')\n"
        )
        experiment_yaml = (
            f"task_type: {inp.data_card.task_type}\n"
            f"target: {inp.data_card.target_column}\n"
            f"metric: {metric_name}\n"
            f"loop_count: {inp.loop_count}\n"
        )
        return PipelineResult(report_md=report_md, final_code=final_code,
                              metrics_history=metrics,
                              experiment_yaml=experiment_yaml)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_mock.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/mock.py tests/test_mock.py
git commit -m "feat: mock backend implementing PipelineBackend contract"
```

---

## Task 4: 샘플 데이터

**Files:**
- Create: `sample_data/sample.csv`
- Create: `sample_data/sample_report.md`

- [ ] **Step 1: 샘플 CSV 생성**

`sample_data/sample.csv` (타이타닉 축약본):

```csv
PassengerId,Pclass,Sex,Age,Fare,Survived
1,3,male,22,7.25,0
2,1,female,38,71.28,1
3,3,female,26,7.92,1
4,1,female,35,53.1,1
5,3,male,35,8.05,0
6,3,male,28,8.46,0
7,1,male,54,51.86,0
8,3,male,2,21.07,0
9,3,female,27,11.13,1
10,2,female,14,30.07,1
```

- [ ] **Step 2: 샘플 리포트 생성**

`sample_data/sample_report.md`:

```markdown
# 분석 리포트 (샘플)

타이타닉 생존자 예측 베이스라인 → 가설 반영 최적화 결과 예시입니다.

## 성능 요약

| 구분 | accuracy |
|---|---|
| 베이스라인 | 0.70 |
| 최종 | 0.82 |
| 향상폭(Δ) | 0.12 |

> ⚠️ 제한된 데이터·환경에서 도출된 결과이므로, 프로덕션 적용 전 반드시 검토가 필요합니다.
```

- [ ] **Step 3: Commit**

```bash
git add sample_data/
git commit -m "test: add sample CSV and report fixtures"
```

---

## Task 5: 공통 테마 (theme.py)

**Files:**
- Create: `ui/theme.py`

UI 렌더링 함수는 Streamlit 런타임이 필요해 단위 테스트 대신 순수 헬퍼만 테스트 가능하게 둔다. 여기서는 순수 문자열 헬퍼 + Streamlit 호출을 분리한다.

- [ ] **Step 1: theme.py 구현**

`ui/theme.py`:

```python
"""화면 간 일관된 스타일·헬퍼."""
from __future__ import annotations

import streamlit as st

# 색상 토큰
PRIMARY = "#2563eb"
SUCCESS = "#16a34a"
WARNING = "#d97706"
MUTED = "#6b7280"

# 결과 신뢰성 경계 문구(기획서 정책)
DISCLAIMER = (
    "⚠️ 제한된 데이터·환경에서 도출된 결과이므로, "
    "프로덕션 적용 전 반드시 검토가 필요합니다."
)

# 3단계 라벨
STEPS = ["1 입력", "2 분석", "3 결과"]


def step_header(active_index: int) -> None:
    """상단 스텝 표시. active_index: 0=입력,1=분석,2=결과."""
    cols = st.columns(len(STEPS))
    for i, (col, label) in enumerate(zip(cols, STEPS)):
        if i < active_index:
            col.markdown(f"✅ **{label}**")
        elif i == active_index:
            col.markdown(f":blue[**▶ {label}**]")
        else:
            col.markdown(f":gray[{label}]")
    st.divider()


def disclaimer_banner() -> None:
    """결과 신뢰성 경계 문구 배너."""
    st.warning(DISCLAIMER)


def page_setup() -> None:
    """페이지 공통 설정. 앱 진입점에서 1회 호출."""
    st.set_page_config(
        page_title="ML 자동화 에이전트",
        page_icon="🤖",
        layout="wide",
    )
```

- [ ] **Step 2: import 동작 확인**

Run: `python -c "import ui.theme; print(ui.theme.STEPS)"`
Expected: `['1 입력', '2 분석', '3 결과']`

- [ ] **Step 3: Commit**

```bash
git add ui/theme.py
git commit -m "feat: shared UI theme helpers (steps, disclaimer, colors)"
```

---

## Task 6: 입력 폼 (input_form.py)

검증·태스크추정 같은 순수 로직은 별도 함수로 빼서 테스트한다. Streamlit 렌더링 함수는 그 로직을 호출한다.

**Files:**
- Create: `ui/input_form.py`
- Test: `tests/test_input_form.py`

- [ ] **Step 1: 순수 로직 테스트 작성**

`tests/test_input_form.py`:

```python
import pandas as pd

from ui.input_form import infer_task_type, build_pipeline_input
from backend.interface import PipelineInput


def test_infer_task_type_binary_is_classification():
    s = pd.Series([0, 1, 1, 0, 1])
    assert infer_task_type(s) == "classification"


def test_infer_task_type_continuous_is_regression():
    s = pd.Series([1.2, 3.4, 5.6, 7.8, 9.1, 2.2, 4.5, 6.7, 8.9, 0.1, 11.0])
    assert infer_task_type(s) == "regression"


def test_infer_task_type_string_is_classification():
    s = pd.Series(["a", "b", "a", "c"])
    assert infer_task_type(s) == "classification"


def test_build_pipeline_input_shape():
    inp = build_pipeline_input(
        csv_path="/tmp/x.csv", loop_count=3, target_column="y",
        task_type="regression", description="d", llm_instruction="가설",
    )
    assert isinstance(inp, PipelineInput)
    assert inp.loop_count == 3
    assert inp.data_card.task_type == "regression"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_input_form.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.input_form'`

- [ ] **Step 3: input_form.py 구현**

`ui/input_form.py`:

```python
"""입력 폼 화면 + 순수 로직(태스크 추정, 입력 구성)."""
from __future__ import annotations

import os
import tempfile
from typing import Optional

import pandas as pd
import streamlit as st

from backend.interface import DataCard, PipelineInput, PipelineBackend
from ui import theme

LOOP_MIN, LOOP_MAX, LOOP_DEFAULT = 1, 10, 3


def infer_task_type(series: pd.Series) -> str:
    """타깃 컬럼 dtype/고유값으로 분류/회귀 추정."""
    if series.dtype == object or str(series.dtype) == "category":
        return "classification"
    nunique = series.nunique(dropna=True)
    # 고유값이 적으면 분류로 간주
    if nunique <= 10:
        return "classification"
    return "regression"


def build_pipeline_input(csv_path: str, loop_count: int, target_column: str,
                         task_type: str, description: str,
                         llm_instruction: str) -> PipelineInput:
    """폼 값들을 PipelineInput으로 조립."""
    card = DataCard(target_column=target_column, task_type=task_type,
                    description=description)
    return PipelineInput(csv_path=csv_path, loop_count=loop_count,
                         data_card=card, llm_instruction=llm_instruction)


def _save_upload(uploaded) -> str:
    """업로드 파일을 임시 경로에 저장하고 경로 반환."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getbuffer())
    return path


def render(backend: PipelineBackend) -> Optional[PipelineInput]:
    """입력 폼 렌더링. '실행'이 눌리고 검증 통과 시 PipelineInput 반환."""
    theme.step_header(0)
    st.subheader("1. 데이터와 분석 의도를 입력하세요")

    uploaded = st.file_uploader("CSV 업로드", type=["csv"])
    if uploaded is None:
        st.info("CSV 파일을 업로드하면 데이터 카드 입력이 활성화됩니다.")
        return None

    csv_path = _save_upload(uploaded)
    df = pd.read_csv(csv_path)
    st.caption(f"행 {df.shape[0]} · 열 {df.shape[1]}")
    st.dataframe(df.head(), use_container_width=True)

    columns = list(df.columns)
    col1, col2 = st.columns(2)
    with col1:
        target_column = st.selectbox("타깃 컬럼(예측 대상)", columns,
                                     index=len(columns) - 1)
    with col2:
        default_task = infer_task_type(df[target_column])
        task_type = st.radio("태스크 종류", ["classification", "regression"],
                             index=0 if default_task == "classification" else 1,
                             horizontal=True)

    description = st.text_area("데이터 카드 — 데이터셋 설명", height=80,
                               placeholder="예) 타이타닉 승객 정보. 생존 여부 예측.")
    llm_instruction = st.text_area(
        "언어모델 입력 — 가설 · 목표 · 평가산식", height=120,
        placeholder="예) 객실 등급(Pclass)이 생존에 미치는 영향 가설을 반영해 "
                    "정확도 기준으로 모델을 개선해줘.",
    )
    loop_count = st.number_input("루프 횟수", min_value=LOOP_MIN, max_value=LOOP_MAX,
                                 value=LOOP_DEFAULT, step=1)

    if st.button("분석 실행 ▶", type="primary"):
        inp = build_pipeline_input(
            csv_path=csv_path, loop_count=int(loop_count),
            target_column=target_column, task_type=task_type,
            description=description, llm_instruction=llm_instruction,
        )
        errors = backend.validate_input(inp)
        if errors:
            for e in errors:
                st.error(e)
            return None
        return inp
    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_input_form.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add ui/input_form.py tests/test_input_form.py
git commit -m "feat: input form screen with task inference and validation"
```

---

## Task 7: 진행 화면 (progress_view.py)

**Files:**
- Create: `ui/progress_view.py`

- [ ] **Step 1: progress_view.py 구현**

`ui/progress_view.py`:

```python
"""진행 상태 실시간 표시 화면."""
from __future__ import annotations

import streamlit as st

from backend.interface import PipelineInput, PipelineBackend, PIPELINE_STAGES
from ui import theme


def render(backend: PipelineBackend, inp: PipelineInput):
    """파이프라인을 실행하며 진행 상태를 실시간 표시. 완료 시 결과 반환."""
    theme.step_header(1)
    st.subheader("2. 파이프라인 실행 중")

    total_loops = inp.loop_count
    progress = st.progress(0.0)
    stage_box = st.empty()
    log_area = st.container()

    done_stages = set()
    with st.status("분석을 시작합니다...", expanded=True) as status:
        for ev in backend.run(inp):
            label = f"[루프 {ev.loop_index}/{total_loops}] {ev.stage} — {ev.message}"
            if ev.status == "done":
                done_stages.add(ev.stage)
            stage_box.markdown(f"**현재:** {label}")
            log_area.write(label)
            progress.progress(min(len(done_stages) / len(PIPELINE_STAGES), 1.0))
        status.update(label="분석 완료", state="complete")

    return backend.get_result()
```

- [ ] **Step 2: import 동작 확인**

Run: `python -c "import ui.progress_view; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add ui/progress_view.py
git commit -m "feat: real-time progress screen streaming pipeline events"
```

---

## Task 8: 보고서 뷰어 (report_viewer.py)

**Files:**
- Create: `ui/report_viewer.py`

- [ ] **Step 1: report_viewer.py 구현**

`ui/report_viewer.py`:

```python
"""최종 보고서 뷰어(리포트/지표/코드/실험설정 탭)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from backend.interface import PipelineResult
from ui import theme


def _metrics_dataframe(result: PipelineResult) -> pd.DataFrame:
    rows = [
        {
            "루프": m.loop_index,
            "지표": m.metric_name,
            "베이스라인": m.baseline,
            "값": m.value,
            "향상폭(Δ)": round(m.value - m.baseline, 4),
        }
        for m in result.metrics_history
    ]
    return pd.DataFrame(rows)


def render(result: PipelineResult) -> None:
    """보고서 화면 렌더링."""
    theme.step_header(2)
    st.subheader("3. 분석 결과")
    theme.disclaimer_banner()

    tab_report, tab_metric, tab_code, tab_yaml = st.tabs(
        ["📄 리포트", "📈 성능지표", "💻 코드", "⚙️ 실험설정"]
    )

    with tab_report:
        st.markdown(result.report_md)
        st.download_button("리포트 다운로드 (.md)", result.report_md,
                           file_name="report.md", mime="text/markdown")

    with tab_metric:
        df = _metrics_dataframe(result)
        if not df.empty:
            chart_df = df.set_index("루프")[["베이스라인", "값"]]
            st.line_chart(chart_df)
            st.dataframe(df, use_container_width=True)
            best = df.iloc[-1]
            st.metric(label=f"최종 {best['지표']}", value=best["값"],
                      delta=best["향상폭(Δ)"])
        else:
            st.info("지표 데이터가 없습니다.")

    with tab_code:
        st.code(result.final_code, language="python")
        st.download_button("코드 다운로드 (.py)", result.final_code,
                           file_name="pipeline.py", mime="text/x-python")

    with tab_yaml:
        st.code(result.experiment_yaml, language="yaml")
        st.download_button("실험설정 다운로드 (.yml)", result.experiment_yaml,
                           file_name="experiment.yml", mime="text/yaml")
```

- [ ] **Step 2: import 동작 확인**

Run: `python -c "import ui.report_viewer; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add ui/report_viewer.py
git commit -m "feat: report viewer with report/metrics/code/yaml tabs"
```

---

## Task 9: 앱 조립 (app.py)

**Files:**
- Create: `app.py`

- [ ] **Step 1: app.py 구현**

`app.py`:

```python
"""ML 자동화 에이전트 — Streamlit 진입점. 세션 상태로 세 화면을 라우팅."""
from __future__ import annotations

import streamlit as st

from backend.mock import MockBackend
from ui import theme, input_form, progress_view, report_viewer


def get_backend():
    """백엔드 주입 지점. 통합 시 MockBackend()를 실제 구현으로 교체."""
    return MockBackend()


def main() -> None:
    theme.page_setup()
    st.title("🤖 ML 자동화 에이전트")

    if "view" not in st.session_state:
        st.session_state.view = "input"
        st.session_state.pipeline_input = None
        st.session_state.result = None

    backend = get_backend()
    view = st.session_state.view

    if view == "input":
        inp = input_form.render(backend)
        if inp is not None:
            st.session_state.pipeline_input = inp
            st.session_state.view = "running"
            st.rerun()

    elif view == "running":
        result = progress_view.render(backend, st.session_state.pipeline_input)
        st.session_state.result = result
        st.session_state.view = "report"
        st.rerun()

    elif view == "report":
        report_viewer.render(st.session_state.result)
        if st.button("새 분석 시작"):
            st.session_state.view = "input"
            st.session_state.pipeline_input = None
            st.session_state.result = None
            st.rerun()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 앱 구문 검증**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: 전체 테스트 실행**

Run: `python -m pytest -v`
Expected: PASS (모든 테스트 통과)

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: assemble app with session-state screen routing"
```

---

## Task 10: E2E 확인 + UI 점검 + README

**Files:**
- Create: `README.md`

- [ ] **Step 1: 앱 수동 실행(E2E)**

Run: `streamlit run app.py`
확인 사항:
- 샘플 CSV(`sample_data/sample.csv`) 업로드 → 미리보기·행/열 수 표시
- 타깃 `Survived` 선택 시 태스크가 classification으로 자동 추정
- 언어모델 입력 작성 후 "분석 실행" → 진행 화면에서 단계/진행률 실시간 갱신
- 보고서 화면에서 4개 탭(리포트/지표/코드/실험설정)과 다운로드 버튼 동작
- 상단 경계 문구 노출, "새 분석 시작"으로 입력 화면 복귀

(스크린샷으로 각 화면 캡처)

- [ ] **Step 2: UI 점검 스킬 적용**

`web-design-guidelines` 스킬로 접근성·UX 점검 후 발견된 문제를 보완하고, 변경이 있으면 커밋한다.

- [ ] **Step 3: README 작성**

`README.md`:

```markdown
# ML 자동화 에이전트 — UI/프론트

ML 파이프라인 자동화 에이전트의 Streamlit 프론트엔드. 입력 폼과 보고서 뷰어를
제공하며, 백엔드는 `PipelineBackend` 인터페이스로 분리되어 있다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 테스트

```bash
python -m pytest -v
```

## 백엔드 통합 가이드

UI는 `backend/interface.py`의 `PipelineBackend` 프로토콜에만 의존한다.
백엔드 팀은 이 프로토콜을 구현한 클래스를 제공하고, `app.py`의 `get_backend()`에서
`MockBackend()`를 그 클래스로 교체하면 통합이 끝난다.

구현해야 할 메서드:
- `validate_input(inp) -> list[str]` : 입력 검증 메시지(빈 리스트면 통과)
- `run(inp) -> Iterator[ProgressEvent]` : 진행 이벤트 스트리밍
- `get_result() -> PipelineResult` : 최종 결과

데이터 형식은 `backend/interface.py`의 dataclass 참고.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with run and backend integration guide"
```

---

## 자체 점검 결과

- **스펙 커버리지**: 입력 폼(Task 6), 보고서 뷰어 4기능=MD+다운로드/지표시각화/코드/진행상태(Task 7,8), 계약+Mock(Task 2,3), UI/UX 기준(theme Task 5 + 점검 Task 10), 백엔드 통합 지점(README Task 10) — 스펙 섹션 모두 대응.
- **플레이스홀더**: 없음(모든 코드·명령·기대출력 명시).
- **타입 일관성**: `PipelineBackend`/`PipelineInput`/`PipelineResult`/`MetricRecord` 등 Task 2 정의가 이후 Task에서 동일 시그니처로 사용됨. Mock의 `MockBackend`는 Protocol 충족(`test_mock_satisfies_protocol`로 검증).
