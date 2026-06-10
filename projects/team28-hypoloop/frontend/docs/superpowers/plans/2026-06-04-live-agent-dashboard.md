# 라이브 에이전트 대시보드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "실행 중" 화면을 에이전트 콘솔 + 실시간 지표를 보여주는 라이브 대시보드로 업그레이드하고, Airtable 디자인 토큰을 앱 전체에 적용한다.

**Architecture:** `ProgressEvent`에 하위호환 필드(kind/detail/metric)를 추가해 한 인프로세스 스트림으로 콘솔·지표·단계를 흘린다. 순수 로직(`DashboardState`)이 이벤트를 분류·누적하고, `dashboard_view`가 렌더한다. mock이 데모용 풍부 이벤트를 emit한다. `theme.py`가 디자인 토큰 + CSS를 주입한다.

**Tech Stack:** Python 3.10, Streamlit 1.56, pandas, pytest

참고 스펙: `docs/superpowers/specs/2026-06-04-live-agent-dashboard-design.md`
작업 위치: `/Users/justice/Desktop/AI 교육` (루트 레이아웃: `app.py`, `ui/`, `backend/`, `tests/`)

---

## 파일 구조

```
backend/interface.py        # 수정: ProgressEvent에 kind/detail/metric 추가
ui/theme.py                 # 수정: 디자인 토큰 + CSS 주입 + 콘솔/배너 HTML 헬퍼
ui/dashboard_logic.py       # 신규: DashboardState (순수 로직, 단위 테스트)
ui/dashboard_view.py        # 신규: 라이브 대시보드 렌더(실행 중 화면)
backend/mock.py             # 수정: llm/code/log/metric 이벤트도 emit
app.py                      # 수정: running 뷰 → dashboard_view 사용
tests/test_interface.py     # 수정: 새 필드 기본값 검증
tests/test_dashboard_logic.py  # 신규: DashboardState 테스트
tests/test_mock.py          # 수정: 풍부 이벤트 emit 검증
```

---

## Task 1: ProgressEvent 계약 확장

**Files:**
- Modify: `backend/interface.py`
- Test: `tests/test_interface.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_interface.py` 끝에 추가:

```python
def test_progress_event_new_fields_default():
    ev = ProgressEvent(stage="EDA", loop_index=0, status="running", message="m")
    assert ev.kind == "stage"
    assert ev.detail == ""
    assert ev.metric is None


def test_progress_event_metric_kind():
    from backend.interface import MetricRecord
    m = MetricRecord(loop_index=1, metric_name="accuracy", baseline=0.7, value=0.8)
    ev = ProgressEvent(stage="튜닝", loop_index=1, status="running",
                       message="지표", kind="metric", metric=m)
    assert ev.kind == "metric"
    assert ev.metric.value == 0.8
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_interface.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'kind'`

- [ ] **Step 3: 구현** — `backend/interface.py`의 `ProgressEvent`와 import 수정:

먼저 import 라인을 다음으로 교체:
```python
from typing import Iterator, List, Optional, Protocol, runtime_checkable
```

`ProgressEvent` 정의를 다음으로 교체:
```python
@dataclass
class ProgressEvent:
    stage: str                    # PIPELINE_STAGES 중 하나
    loop_index: int               # 0 = 베이스라인
    status: str                   # "running" | "done" | "failed"
    message: str                  # 사용자에게 보일 한 줄 설명
    kind: str = "stage"           # "stage"|"llm"|"code"|"log"|"metric"
    detail: str = ""              # 생성 코드 / LLM 출력 / 로그 본문
    metric: "Optional[MetricRecord]" = None  # kind=="metric"일 때 실시간 지표
```

(주의: `MetricRecord`는 같은 파일 아래쪽에 정의돼 있으므로 문자열 어노테이션 사용. 파일 상단에 `from __future__ import annotations`가 이미 있으면 따옴표 없이도 가능하나, 안전하게 따옴표 유지.)

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_interface.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/interface.py tests/test_interface.py
git commit -m "feat: extend ProgressEvent with kind/detail/metric (backward-compatible)"
```

---

## Task 2: DashboardState 순수 로직

**Files:**
- Create: `ui/dashboard_logic.py`
- Test: `tests/test_dashboard_logic.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_dashboard_logic.py`:

```python
from backend.interface import ProgressEvent, MetricRecord
from ui.dashboard_logic import DashboardState, ConsoleItem


def ev(kind="stage", stage="EDA", loop=0, status="running", message="m",
       detail="", metric=None):
    return ProgressEvent(stage=stage, loop_index=loop, status=status,
                         message=message, kind=kind, detail=detail, metric=metric)


def test_stage_event_tracks_current_and_done():
    s = DashboardState()
    s.apply(ev(kind="stage", stage="베이스라인", loop=0, status="running"))
    assert s.current_stage == "베이스라인"
    assert s.current_loop == 0
    s.apply(ev(kind="stage", stage="베이스라인", loop=0, status="done"))
    assert "베이스라인" in s.stages_done


def test_console_accumulates_llm_code_log():
    s = DashboardState()
    s.apply(ev(kind="llm", detail="Solar 호출"))
    s.apply(ev(kind="code", detail="print(1)"))
    s.apply(ev(kind="log", message="로그줄"))
    assert len(s.console) == 3
    assert [c.kind for c in s.console] == ["llm", "code", "log"]
    assert s.console[0].text == "Solar 호출"
    assert s.console[2].text == "로그줄"   # detail 비면 message 사용


def test_console_capped_at_max():
    s = DashboardState(max_console=5)
    for i in range(8):
        s.apply(ev(kind="log", message=f"l{i}"))
    assert len(s.console) == 5
    assert s.console[0].text == "l3"   # 최근 5개만


def test_metric_event_accumulates_and_latest():
    s = DashboardState()
    m0 = MetricRecord(loop_index=0, metric_name="accuracy", baseline=0.7, value=0.7)
    m1 = MetricRecord(loop_index=1, metric_name="accuracy", baseline=0.7, value=0.8)
    s.apply(ev(kind="metric", metric=m0))
    s.apply(ev(kind="metric", metric=m1))
    assert len(s.metrics) == 2
    assert s.latest_metric().value == 0.8


def test_latest_metric_none_when_empty():
    assert DashboardState().latest_metric() is None


def test_stage_progress_fraction():
    s = DashboardState()
    s.apply(ev(kind="stage", stage="계획수립", status="done"))
    s.apply(ev(kind="stage", stage="EDA", status="done"))
    # 전체 6단계 중 2개 완료 → 1/3
    assert round(s.stage_progress(6), 3) == 0.333
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_dashboard_logic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.dashboard_logic'`

- [ ] **Step 3: 구현** — `ui/dashboard_logic.py`:

```python
"""대시보드 순수 로직: 이벤트 스트림을 콘솔/지표/단계 상태로 분류·누적."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from backend.interface import ProgressEvent, MetricRecord

CONSOLE_KINDS = ("llm", "code", "log")
DEFAULT_MAX_CONSOLE = 30


@dataclass
class ConsoleItem:
    kind: str          # "llm" | "code" | "log"
    text: str
    loop_index: int


@dataclass
class DashboardState:
    """이벤트를 적용해 대시보드가 그릴 상태를 누적한다."""
    max_console: int = DEFAULT_MAX_CONSOLE
    console: List[ConsoleItem] = field(default_factory=list)
    metrics: List[MetricRecord] = field(default_factory=list)
    stages_done: Set[str] = field(default_factory=set)
    current_stage: str = ""
    current_loop: int = 0

    def apply(self, ev: ProgressEvent) -> None:
        self.current_stage = ev.stage
        self.current_loop = ev.loop_index
        if ev.kind == "stage":
            if ev.status == "done":
                self.stages_done.add(ev.stage)
        elif ev.kind in CONSOLE_KINDS:
            text = ev.detail if ev.detail else ev.message
            self.console.append(ConsoleItem(ev.kind, text, ev.loop_index))
            if len(self.console) > self.max_console:
                self.console = self.console[-self.max_console:]
        elif ev.kind == "metric" and ev.metric is not None:
            self.metrics.append(ev.metric)

    def latest_metric(self) -> Optional[MetricRecord]:
        return self.metrics[-1] if self.metrics else None

    def stage_progress(self, total_stages: int) -> float:
        if total_stages <= 0:
            return 0.0
        return min(len(self.stages_done) / total_stages, 1.0)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_dashboard_logic.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add ui/dashboard_logic.py tests/test_dashboard_logic.py
git commit -m "feat: DashboardState pure logic for live event aggregation"
```

---

## Task 3: mock.py 풍부 이벤트 emit

**Files:**
- Modify: `backend/mock.py`
- Test: `tests/test_mock.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_mock.py` 끝에 추가:

```python
def test_run_emits_rich_event_kinds(csv_path):
    backend = MockBackend()
    events = list(backend.run(make_input(csv_path, loop_count=2)))
    kinds = {e.kind for e in events}
    assert "stage" in kinds
    assert "llm" in kinds
    assert "code" in kinds
    assert "metric" in kinds
    # metric 이벤트는 MetricRecord를 실제로 담는다
    metric_events = [e for e in events if e.kind == "metric"]
    assert len(metric_events) >= 1
    assert metric_events[0].metric is not None
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_mock.py::test_run_emits_rich_event_kinds -v`
Expected: FAIL — `assert 'llm' in {'stage'}`

- [ ] **Step 3: 구현** — `backend/mock.py`의 `run()` 메서드를 다음으로 교체 (베이스라인·루프 단계에 llm/code/log/metric 이벤트를 추가):

```python
    def run(self, inp: PipelineInput) -> Iterator[ProgressEvent]:
        is_clf = inp.data_card.task_type == "classification"
        metric_name = "accuracy" if is_clf else "rmse"
        baseline = 0.70 if is_clf else 0.50
        metrics: List[MetricRecord] = []

        def stage_evt(stage, loop, status, msg):
            return ProgressEvent(stage=stage, loop_index=loop, status=status,
                                 message=msg)

        def info_evt(stage, loop, kind, text):
            return ProgressEvent(stage=stage, loop_index=loop, status="running",
                                 message=text, kind=kind, detail=text)

        # 계획수립 / EDA / 베이스라인
        for stage in PIPELINE_STAGES[:3]:
            yield stage_evt(stage, 0, "running", f"{stage} 진행 중…")
            yield info_evt(stage, 0, "llm",
                           f"Solar API 호출 — {stage} 단계 계획 생성")
            time.sleep(self._step_delay)
            yield info_evt(stage, 0, "code",
                           f"# {stage} 자동 생성 코드 (데모)\nimport pandas as pd\n"
                           f"df = pd.read_csv('data.csv')")
            yield stage_evt(stage, 0, "done", f"{stage} 완료")
        metrics.append(MetricRecord(loop_index=0, metric_name=metric_name,
                                    baseline=baseline, value=baseline))
        yield ProgressEvent(stage="베이스라인", loop_index=0, status="running",
                            message=f"베이스라인 {metric_name}={baseline}",
                            kind="metric", metric=metrics[-1])

        # 개선 루프
        for loop in range(1, inp.loop_count + 1):
            yield info_evt("피처엔지니어링", loop, "llm",
                           f"Solar API — 루프 {loop} 가설 생성 및 파생변수 제안")
            for stage in PIPELINE_STAGES[3:5]:
                yield stage_evt(stage, loop, "running", f"루프 {loop}: {stage} 진행 중…")
                time.sleep(self._step_delay)
                yield info_evt(stage, loop, "code",
                               f"# 루프 {loop} {stage} 코드 (데모)\n"
                               f"model.fit(X_train, y_train)")
                yield stage_evt(stage, loop, "done", f"루프 {loop}: {stage} 완료")
            if is_clf:
                value = round(min(baseline + 0.04 * loop, 0.95), 4)
            else:
                value = round(max(baseline - 0.03 * loop, 0.10), 4)
            metrics.append(MetricRecord(loop_index=loop, metric_name=metric_name,
                                        baseline=baseline, value=value))
            yield ProgressEvent(stage="튜닝", loop_index=loop, status="running",
                                message=f"루프 {loop} {metric_name}={value}",
                                kind="metric", metric=metrics[-1])

        # 리포트
        yield stage_evt("리포트", inp.loop_count, "running", "리포트 생성 중…")
        yield info_evt("리포트", inp.loop_count, "log", "최종 리포트·코드·yml 작성")
        time.sleep(self._step_delay)
        self._result = self._build_result(inp, metrics, metric_name)
        yield stage_evt("리포트", inp.loop_count, "done", "완료")
```

- [ ] **Step 4: 통과 확인 (신규 + 기존 모두)**

Run: `python -m pytest tests/test_mock.py -v`
Expected: PASS (기존 + 신규 모두 통과). 특히 `test_run_streams_events_in_stage_order`(모든 단계 등장 + 마지막 done)와 `test_run_emits_rich_event_kinds` 통과.

- [ ] **Step 5: Commit**

```bash
git add backend/mock.py tests/test_mock.py
git commit -m "feat: mock backend emits rich llm/code/log/metric events for dashboard"
```

---

## Task 4: 디자인 토큰 + CSS 주입 (theme.py)

**Files:**
- Modify: `ui/theme.py`

순수 렌더라 단위 테스트 대신 import·토큰 존재로 검증하고, Task 7에서 시각 확인한다.

- [ ] **Step 1: theme.py 상단 토큰 교체/확장** — 기존 색상 토큰 블록(`PRIMARY = ...` 등)을 다음으로 교체(기존 `DISCLAIMER`, `STEPS`, `step_header`, `disclaimer_banner`, `page_setup`는 유지하되 page_setup만 아래 Step 3에서 수정):

`import streamlit as st` 아래에 토큰 정의:
```python
# --- Airtable 디자인 토큰 ---
INK = PRIMARY = "#181d26"
PRIMARY_ACTIVE = "#0d1218"
CANVAS = "#ffffff"
SURFACE_SOFT = "#f8fafc"
SURFACE_STRONG = "#e0e2e6"
SURFACE_DARK = "#181d26"
HAIRLINE = "#dddddd"
BODY = "#333840"
MUTED = "#41454d"
LINK = "#1b61c9"
SUCCESS = "#006400"
WARNING = "#d97706"
# 시그니처 surface
CORAL = "#aa2d00"
FOREST = "#0a2e0e"
CREAM = "#f5e9d4"
PEACH = "#fcab79"
MINT = "#a8d8c4"
YELLOW = "#f4d35e"
MUSTARD = "#d9a441"

# 단계별 시그니처 surface (voltage 모먼트)
STAGE_SURFACE = {
    "계획수립": SURFACE_DARK, "EDA": FOREST, "베이스라인": CORAL,
    "피처엔지니어링": FOREST, "튜닝": CORAL, "리포트": SURFACE_DARK,
}
```

(주의: 기존 `SUCCESS`/`WARNING`/`MUTED`/`PRIMARY`가 이미 있으면 중복 정의 제거하고 위 값으로 통일.)

- [ ] **Step 2: CSS 상수 추가** — theme.py에 추가:

```python
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Inter+Tight:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; color: #333840; }
h1, h2, h3 { font-family: 'Inter Tight', 'Inter', system-ui, sans-serif; color: #181d26; font-weight: 500; letter-spacing: 0; }
h1 { font-weight: 400; }
/* primary 버튼: near-black, 12px */
div.stButton > button[kind="primary"] {
  background: #181d26; color: #ffffff; border: none; border-radius: 12px;
  padding: 16px 24px; font-weight: 500;
}
div.stButton > button[kind="primary"]:active { background: #0d1218; }
/* secondary 버튼: 흰 배경 + 헤어라인 */
div.stButton > button[kind="secondary"] {
  background: #ffffff; color: #181d26; border: 1px solid #dddddd; border-radius: 12px;
  padding: 16px 24px; font-weight: 500;
}
/* 대시보드 콘솔/배너 */
.hl-banner { border-radius: 12px; padding: 16px 20px; color: #ffffff;
  font-weight: 500; margin-bottom: 16px; }
.hl-console { background: #f8fafc; border: 1px solid #dddddd; border-radius: 10px;
  padding: 16px; max-height: 520px; overflow-y: auto; }
.hl-item { display: flex; gap: 8px; padding: 6px 0; font-size: 14px; color: #333840;
  border-bottom: 1px solid #eef1f4; }
.hl-item .ic { flex: 0 0 20px; }
.hl-code { background: #181d26; color: #e6e8eb; border-radius: 8px; padding: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
  white-space: pre-wrap; margin: 4px 0; }
.hl-metric-card { background: #f5e9d4; border-radius: 10px; padding: 16px; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
```

- [ ] **Step 3: page_setup에서 CSS 주입** — 기존 `page_setup()` 함수 본문 끝(`st.set_page_config(...)` 호출 다음)에 `inject_css()` 추가:

```python
def page_setup() -> None:
    """페이지 공통 설정 + 디자인 CSS 주입. 앱 진입점에서 1회 호출."""
    st.set_page_config(
        page_title="ML 자동화 에이전트",
        page_icon="🤖",
        layout="wide",
    )
    inject_css()
```

- [ ] **Step 4: 콘솔/배너 HTML 헬퍼 추가** — theme.py에 추가:

```python
import html as _html


def stage_banner_html(stage: str, loop: int, total_loops: int) -> str:
    """현재 단계를 시그니처 surface 배너로."""
    bg = STAGE_SURFACE.get(stage, SURFACE_DARK)
    label = _html.escape(f"▶ 현재: {stage}  ·  루프 {loop}/{total_loops}")
    return f'<div class="hl-banner" style="background:{bg}">{label}</div>'


def console_html(items) -> str:
    """콘솔 피드(ConsoleItem 리스트)를 스타일된 HTML로."""
    icons = {"llm": "🧠", "code": "💻", "log": "•"}
    rows = []
    for it in items:
        if it.kind == "code":
            rows.append(
                f'<div class="hl-item"><span class="ic">💻</span>'
                f'<div class="hl-code">{_html.escape(it.text)}</div></div>'
            )
        else:
            ic = icons.get(it.kind, "•")
            rows.append(
                f'<div class="hl-item"><span class="ic">{ic}</span>'
                f'<span>{_html.escape(it.text)}</span></div>'
            )
    return '<div class="hl-console">' + "".join(rows) + "</div>"
```

- [ ] **Step 5: import·토큰 동작 확인**

Run: `python -c "import ui.theme as t; print(t.CORAL, t.STAGE_SURFACE['베이스라인']); print('css len', len(t._CSS)); print('helpers', callable(t.console_html), callable(t.stage_banner_html), callable(t.inject_css))"`
Expected: `#aa2d00 #aa2d00`, css len > 0, `helpers True True True`

- [ ] **Step 6: 기존 테스트 회귀 확인**

Run: `python -m pytest -q`
Expected: 기존 테스트 전부 통과(theme 변경이 input_form/report 등 깨지 않음).

- [ ] **Step 7: Commit**

```bash
git add ui/theme.py
git commit -m "feat: apply Airtable design tokens + CSS injection + console/banner helpers"
```

---

## Task 5: dashboard_view 라이브 화면

**Files:**
- Create: `ui/dashboard_view.py`

- [ ] **Step 1: 구현** — `ui/dashboard_view.py`:

```python
"""실행 중 라이브 대시보드: 에이전트 콘솔 + 실시간 지표."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from backend.interface import PipelineInput, PipelineBackend, PIPELINE_STAGES
from ui import theme
from ui.dashboard_logic import DashboardState


def _metrics_df(metrics) -> pd.DataFrame:
    rows = [{"루프": m.loop_index, "베이스라인": m.baseline, "값": m.value}
            for m in metrics]
    return pd.DataFrame(rows).set_index("루프") if rows else pd.DataFrame()


def render(backend: PipelineBackend, inp: PipelineInput):
    """파이프라인을 실행하며 라이브 대시보드를 갱신. 완료 시 결과 반환."""
    theme.step_header(1)
    st.subheader("2. 에이전트 실행 — 라이브 대시보드")
    st.caption("🧠 LLM 호출 · 💻 생성 코드는 현재 데모(시뮬레이션)이며, "
               "데이터 적재·지표는 실제 백엔드를 사용합니다.")

    banner = st.empty()
    progress = st.progress(0.0)
    col_console, col_metric = st.columns([2, 1])
    console_box = col_console.empty()
    metric_box = col_metric.empty()
    chart_box = col_metric.empty()

    state = DashboardState()
    for ev in backend.run(inp):
        state.apply(ev)
        banner.markdown(
            theme.stage_banner_html(state.current_stage, state.current_loop,
                                    inp.loop_count),
            unsafe_allow_html=True)
        progress.progress(state.stage_progress(len(PIPELINE_STAGES)))
        console_box.markdown(theme.console_html(state.console),
                             unsafe_allow_html=True)
        m = state.latest_metric()
        if m is not None:
            metric_box.metric(f"최신 {m.metric_name}", m.value,
                              round(m.value - m.baseline, 4))
            df = _metrics_df(state.metrics)
            if not df.empty:
                chart_box.line_chart(df)

    progress.progress(1.0)
    return backend.get_result()
```

- [ ] **Step 2: import 동작 확인**

Run: `python -c "import ui.dashboard_view; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add ui/dashboard_view.py
git commit -m "feat: live dashboard view (agent console + real-time metrics)"
```

---

## Task 6: app.py 라우팅 연결

**Files:**
- Modify: `app.py`

- [ ] **Step 1: import 교체** — `app.py`의 ui import 라인을 다음으로 교체:

```python
from ui import theme, input_form, dashboard_view, report_viewer
```

(`progress_view`는 더 이상 기본 흐름에서 쓰지 않지만 파일은 남겨둔다.)

- [ ] **Step 2: running 뷰 교체** — `app.py`의 `elif view == "running":` 블록에서 `progress_view.render(...)` 호출을 `dashboard_view.render(...)`로 교체:

```python
    elif view == "running":
        result = dashboard_view.render(backend, st.session_state.pipeline_input)
        st.session_state.result = result
        st.session_state.view = "report"
        st.rerun()
```

(통합 브랜치 버전이라면 기존 try/except 구조를 유지하되 내부 호출만 `dashboard_view.render`로 교체.)

- [ ] **Step 3: 구문·import 확인**

Run: `python -c "import ast; ast.parse(open('app.py').read()); import app; print('ok')"`
Expected: `ok`

- [ ] **Step 4: 전체 테스트**

Run: `python -m pytest -q`
Expected: 전부 통과.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: route running view to live dashboard"
```

---

## Task 7: E2E 라이브 확인

**Files:** (없음 — 검증)

- [ ] **Step 1: 앱 실행 및 흐름 확인**

`.claude/launch.json`의 `streamlit-ui`로 앱을 띄우고(또는 `streamlit run app.py`), 다음을 확인:
- 입력 화면: 폰트(Inter)·near-black 기본 버튼·헤어라인 보조 버튼 적용
- 샘플 CSV 업로드 → 분석 실행 → **라이브 대시보드**:
  - 상단 시그니처 surface 단계 배너(coral/forest/dark가 단계별로 바뀜)
  - 진행률 바
  - 좌측 에이전트 콘솔: 🧠 LLM · 💻 코드(다크 블록) · 로그가 실시간 누적
  - 우측 지표: 최신 지표 카드(Δ) + 라인차트 실시간 갱신
  - "데모(시뮬레이션)" 안내 노출
- 완료 후 결과 화면(report_viewer) 정상

(각 화면 스크린샷 캡처)

- [ ] **Step 2: 디자인 토큰 점검**

배너/콘솔/버튼 색·라운드가 토큰과 일치하는지 스크린샷으로 확인. 디스플레이가 굵게(700) 되지 않았는지 확인.

- [ ] **Step 3: 회귀 최종 확인**

Run: `python -m pytest -q`
Expected: 전부 통과.

---

## 자체 점검 결과

- **스펙 커버리지**: 이벤트 계약 확장(Task 1=스펙 §2), DashboardState(Task 2=§3·§4), mock 풍부 이벤트(Task 3=§3·§6), 디자인 토큰/CSS/헬퍼(Task 4=§9), dashboard_view(Task 5=§3·§5·§9.3), app 라우팅(Task 6=§3), E2E·시각 확인(Task 7=§7). 통합 브랜치 adapter 풍부 이벤트는 별도 전파(스펙 §3.1 비고) — 본 계획은 로컬 pure 프론트 대상.
- **플레이스홀더**: 없음(모든 코드·명령·기대출력 명시).
- **타입 일관성**: `ProgressEvent.kind/detail/metric`(Task1) → `DashboardState.apply`(Task2) → mock emit(Task3) → `console_html`/`stage_banner_html`(Task4) → `dashboard_view`(Task5)에서 동일 필드·`ConsoleItem`(kind/text/loop_index) 사용. `DashboardState(max_console=...)`, `latest_metric()`, `stage_progress(total)` 시그니처 일관.
