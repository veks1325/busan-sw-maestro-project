# Streamlit 가설 중심 앱 재설계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프론트를 프로젝트·가설 중심 Streamlit 앱으로 재설계한다 — 사이드바(프로젝트 고정+가설 추가), 대시보드 점수 차트(Plotly, 점 클릭→보고서), 가설 등록(입력+라이브 에이전트 활동), 보고서. 데이터는 목 store 계층.

**Architecture:** `store/`(Protocol+MockStore)가 가설/실행/점수/보고서를 관리(세션 보관, feat/backend 계약 미러). `ui/` 컴포넌트가 사이드바·대시보드·등록·보고서를 렌더하고 `app.py`가 셸+라우팅. 순수 로직(MockStore, AgentActivityState, scores_to_figure_data)은 단위 테스트, Streamlit 렌더는 수동 확인.

**Tech Stack:** Python 3.10, Streamlit 1.56, plotly 5.9, pandas, pytest

참고 스펙: `docs/superpowers/specs/2026-06-05-hypothesis-app-design.md`
작업 위치: `/Users/justice/Desktop/AI 교육` (루트 레이아웃). 이모지 미사용, 차분한 디자인.

---

## 파일 구조

```
app.py                       # 셸: page_config, 테마, get_store(), 사이드바, 라우팅
store/__init__.py
store/types.py               # Project / Hypothesis / AgentEvent
store/base.py                # HypoStore Protocol
store/mock.py                # MockStore (세션 보관 + 시뮬레이션 run)
ui/__init__.py
ui/theme.py                  # 토큰 + CSS (이모지 없음)
ui/agent_status.py           # AgentActivityState(순수) + 라이브 콘솔 렌더
ui/dashboard_view.py         # scores_to_figure_data(순수) + Plotly 차트 렌더
ui/sidebar.py                # 프로젝트 고정 + 가설 목록 + 새 가설
ui/hypothesis_register.py    # 입력 폼 + 라이브 영역
ui/report_view.py            # 보고서
tests/test_store_mock.py
tests/test_agent_status.py
tests/test_dashboard_data.py
requirements.txt             # + plotly
```

---

## Task 1: 골격 + 의존성

**Files:**
- Modify: `requirements.txt`
- Create: `store/__init__.py`, `ui/__init__.py` (빈), `tests/__init__.py`(있으면 유지)

- [ ] **Step 1: requirements.txt에 plotly 추가** (기존 줄 유지 — 기존 API 테스트가 fastapi/httpx를 import하므로 제거하면 안 됨). 파일에 다음 한 줄을 추가:
```
plotly>=5.9
```
(최종 requirements.txt는 streamlit/pandas/pytest/fastapi/uvicorn[standard]/httpx + plotly)

- [ ] **Step 2: 설치 확인** — Run: `pip install -r requirements.txt` (streamlit/pandas/plotly/pytest 충족).

- [ ] **Step 3: 패키지 생성**
```bash
mkdir -p store ui tests && : > store/__init__.py && : > ui/__init__.py && [ -f tests/__init__.py ] || : > tests/__init__.py
```

- [ ] **Step 4: Commit**
```bash
git add requirements.txt store/__init__.py ui/__init__.py tests/__init__.py
git commit -m "chore: scaffold hypothesis-app packages + plotly dep"
```

---

## Task 2: 데이터 타입 + store 계약

**Files:**
- Create: `store/types.py`, `store/base.py`
- Test: `tests/test_store_mock.py` (타입 부분)

- [ ] **Step 1: 타입 테스트 작성** — `tests/test_store_mock.py`:
```python
from store.types import Project, Hypothesis, AgentEvent


def test_hypothesis_defaults():
    h = Hypothesis(hypothesis_id="h1", project_id="p1", content="가설",
                   max_experiments=3, parallel_count=1)
    assert h.status == "registered"
    assert h.best_score is None
    assert h.score_history == []


def test_agent_event_fields():
    ev = AgentEvent(phase="EDA", kind="metric", text="점수", score=0.8)
    assert ev.kind == "metric" and ev.score == 0.8


def test_project_fields():
    p = Project(project_id="p1", name="타이타닉")
    assert p.name == "타이타닉"
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_store_mock.py -q` → FAIL (no module store.types).

- [ ] **Step 3: 구현** — `store/types.py`:
```python
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


@dataclass
class AgentEvent:
    phase: str                    # 단계명
    kind: str                     # "step" | "tool" | "code" | "log" | "metric"
    text: str
    score: Optional[float] = None  # kind=="metric"일 때 0~1
```

`store/base.py`:
```python
"""HypoStore 계약 — 프론트가 의존하는 데이터 인터페이스 (Mock/Backend 교체 지점)."""
from __future__ import annotations

from typing import Iterator, List, Protocol, Tuple, runtime_checkable

from store.types import Project, Hypothesis, AgentEvent


@runtime_checkable
class HypoStore(Protocol):
    def get_project(self) -> Project: ...
    def list_hypotheses(self) -> List[Hypothesis]: ...
    def create_hypothesis(self, content: str, max_experiments: int,
                          parallel_count: int) -> Hypothesis: ...
    def run(self, hypothesis_id: str) -> Iterator[AgentEvent]: ...
    def get_report(self, hypothesis_id: str) -> Hypothesis: ...
    def best_scores(self) -> List[Tuple[Hypothesis, float]]: ...
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_store_mock.py -q` → PASS (3 passed).

- [ ] **Step 5: Commit**
```bash
git add store/types.py store/base.py tests/test_store_mock.py
git commit -m "feat: store types + HypoStore protocol"
```

---

## Task 3: MockStore

**Files:**
- Create: `store/mock.py`
- Test: `tests/test_store_mock.py` (append)

- [ ] **Step 1: 테스트 추가** — `tests/test_store_mock.py` 끝에:
```python
from store.mock import MockStore
from store.base import HypoStore


def test_mockstore_satisfies_protocol():
    assert isinstance(MockStore(), HypoStore)


def test_create_and_list():
    s = MockStore()
    assert s.list_hypotheses() == []
    h = s.create_hypothesis("Pclass 영향", max_experiments=3, parallel_count=1)
    assert h.status == "registered"
    assert len(s.list_hypotheses()) == 1


def test_run_emits_events_and_completes():
    s = MockStore(step_delay=0.0)
    h = s.create_hypothesis("가설", max_experiments=3, parallel_count=1)
    events = list(s.run(h.hypothesis_id))
    assert len(events) > 0
    kinds = {e.kind for e in events}
    assert "step" in kinds and "metric" in kinds
    done = s.get_report(h.hypothesis_id)
    assert done.status == "done"
    assert done.best_score is not None and 0.0 <= done.best_score <= 1.0
    assert len(done.score_history) == 3          # max_experiments회
    assert done.report_md.startswith("#")


def test_best_scores_only_done():
    s = MockStore(step_delay=0.0)
    h1 = s.create_hypothesis("a", 2, 1)
    s.create_hypothesis("b", 2, 1)               # 실행 안 함 → 제외
    list(s.run(h1.hypothesis_id))
    bs = s.best_scores()
    assert len(bs) == 1
    assert bs[0][0].hypothesis_id == h1.hypothesis_id
    assert bs[0][1] == s.get_report(h1.hypothesis_id).best_score


def test_get_report_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        MockStore().get_report("nope")
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_store_mock.py -q` → FAIL (no store.mock).

- [ ] **Step 3: 구현** — `store/mock.py`:
```python
"""세션 보관 + 에이전트 시뮬레이션 MockStore. 순수 Python(Streamlit 비의존)."""
from __future__ import annotations

import time
import uuid
from typing import Dict, Iterator, List, Tuple

from store.types import Project, Hypothesis, AgentEvent

PHASES = ["계획 수립", "EDA", "실험 설계", "학습 코드 생성", "학습/평가", "보고서 작성"]
_STEP_DELAY = 0.04


class MockStore:
    """HypoStore 구현(데모용). 가설을 메모리에 보관하고 run()을 시뮬레이션한다."""

    def __init__(self, step_delay: float = _STEP_DELAY) -> None:
        self._step_delay = step_delay
        self._project = Project(project_id="titanic", name="타이타닉 생존 예측")
        self._hyps: Dict[str, Hypothesis] = {}
        self._order: List[str] = []
        self._base: Dict[str, float] = {}   # 가설별 점수 기준선
        self._seq = 0

    def get_project(self) -> Project:
        return self._project

    def list_hypotheses(self) -> List[Hypothesis]:
        return [self._hyps[i] for i in self._order]

    def create_hypothesis(self, content: str, max_experiments: int,
                          parallel_count: int) -> Hypothesis:
        hid = str(uuid.uuid4())
        h = Hypothesis(hypothesis_id=hid, project_id=self._project.project_id,
                       content=content, max_experiments=max_experiments,
                       parallel_count=parallel_count)
        self._hyps[hid] = h
        self._order.append(hid)
        self._base[hid] = 0.55 + 0.07 * (self._seq % 5)   # 가설마다 다른 기준선
        self._seq += 1
        return h

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
        h.analysis_text = (
            f"총 {h.max_experiments}회 실험에서 최고 점수 {h.best_score}를 달성했습니다. "
            f"실험을 거듭할수록 점수가 향상되는 경향을 보였습니다."
        )
        h.report_md = (
            f"# 분석 보고서\n\n"
            f"## 가설\n\n> {h.content}\n\n"
            f"## 성능 요약\n\n"
            f"- 최고 점수: **{h.best_score}** (0~1, 높을수록 좋음)\n"
            f"- 실험 횟수: {h.max_experiments} (병렬 {h.parallel_count})\n\n"
            f"## 실험 결과 분석\n\n{h.analysis_text}\n"
        )
        h.status = "done"
        yield AgentEvent("보고서 작성", "log", "보고서 작성 완료")

    def get_report(self, hypothesis_id: str) -> Hypothesis:
        return self._hyps[hypothesis_id]

    def best_scores(self) -> List[Tuple[Hypothesis, float]]:
        return [(h, h.best_score) for h in self.list_hypotheses()
                if h.status == "done" and h.best_score is not None]
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_store_mock.py -q` → PASS (8 passed).

- [ ] **Step 5: Commit**
```bash
git add store/mock.py tests/test_store_mock.py
git commit -m "feat: MockStore with simulated agent run + scores/report"
```

---

## Task 4: 라이브 에이전트 상태 + 콘솔

**Files:**
- Create: `ui/agent_status.py`
- Test: `tests/test_agent_status.py`

- [ ] **Step 1: 테스트 작성** — `tests/test_agent_status.py`:
```python
from store.types import AgentEvent
from ui.agent_status import AgentActivityState


def ev(kind="step", phase="EDA", text="t", score=None):
    return AgentEvent(phase=phase, kind=kind, text=text, score=score)


def test_apply_tracks_phase_and_lines():
    s = AgentActivityState()
    s.apply(ev(kind="step", phase="계획 수립", text="시작"))
    assert s.current_phase == "계획 수립"
    assert len(s.lines) == 1


def test_metric_collects_scores():
    s = AgentActivityState()
    s.apply(ev(kind="metric", text="점수", score=0.7))
    s.apply(ev(kind="metric", text="점수", score=0.8))
    assert s.scores == [0.7, 0.8]
    assert s.latest_score() == 0.8


def test_lines_capped():
    s = AgentActivityState(max_lines=5)
    for i in range(8):
        s.apply(ev(text=f"l{i}"))
    assert len(s.lines) == 5
    assert s.lines[0].text == "l3"


def test_latest_score_none_when_empty():
    assert AgentActivityState().latest_score() is None
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_agent_status.py -q` → FAIL.

- [ ] **Step 3: 구현** — `ui/agent_status.py`:
```python
"""라이브 에이전트 활동 — 순수 상태(AgentActivityState) + Streamlit 콘솔 렌더."""
from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from typing import List, Optional

import streamlit as st

from store.types import AgentEvent

DEFAULT_MAX_LINES = 40


@dataclass
class ConsoleLine:
    kind: str
    text: str
    phase: str


@dataclass
class AgentActivityState:
    max_lines: int = DEFAULT_MAX_LINES
    lines: List[ConsoleLine] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    current_phase: str = ""

    def apply(self, ev: AgentEvent) -> None:
        self.current_phase = ev.phase
        if ev.kind == "metric" and ev.score is not None:
            self.scores.append(ev.score)
        self.lines.append(ConsoleLine(ev.kind, ev.text, ev.phase))
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines:]

    def latest_score(self) -> Optional[float]:
        return self.scores[-1] if self.scores else None


# 종류별 라벨(이모지 없이 텍스트로 구분)
_LABEL = {"step": "단계", "tool": "툴", "code": "코드", "log": "로그", "metric": "점수"}


def console_html(lines: List[ConsoleLine]) -> str:
    rows = []
    for ln in lines:
        tag = _LABEL.get(ln.kind, ln.kind)
        if ln.kind == "code":
            rows.append(
                f'<div class="hl-line"><span class="hl-tag">{tag}</span>'
                f'<pre class="hl-code">{_html.escape(ln.text)}</pre></div>'
            )
        else:
            rows.append(
                f'<div class="hl-line"><span class="hl-tag">{tag}</span>'
                f'<span class="hl-txt">{_html.escape(ln.text)}</span></div>'
            )
    return '<div class="hl-console">' + "".join(rows) + "</div>"


def render_console(state: AgentActivityState) -> None:
    """현재 상태를 콘솔로 렌더(컨테이너 안에서 호출)."""
    if state.current_phase:
        st.markdown(f'<div class="hl-phase">현재 단계 · {_html.escape(state.current_phase)}</div>',
                    unsafe_allow_html=True)
    st.markdown(console_html(state.lines), unsafe_allow_html=True)
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_agent_status.py -q` → PASS (4 passed). 또한 `python -c "import ui.agent_status; print('ok')"` → ok.

- [ ] **Step 5: Commit**
```bash
git add ui/agent_status.py tests/test_agent_status.py
git commit -m "feat: live agent activity state + console renderer"
```

---

## Task 5: 디자인 테마

**Files:**
- Create: `ui/theme.py`

순수 렌더라 import 확인으로 검증.

- [ ] **Step 1: 구현** — `ui/theme.py`:
```python
"""차분한 디자인 토큰 + CSS 주입 (이모지 없음)."""
from __future__ import annotations

import streamlit as st

# 색상 토큰 — 부드러운 뉴트럴 + 단일 포인트(인디고)
INK = "#1f2430"
BODY = "#3b4252"
MUTED = "#6b7280"
CANVAS = "#ffffff"
SOFT = "#f6f7f9"
HAIRLINE = "#e3e6ea"
ACCENT = "#4f6bed"
ACCENT_SOFT = "#eef1fd"
SUCCESS = "#2f9e6e"
RUNNING = "#c08a2d"

# 상태 배지 색
STATUS_COLOR = {"registered": MUTED, "running": RUNNING, "done": SUCCESS}
STATUS_LABEL = {"registered": "등록됨", "running": "실행 중", "done": "완료"}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family:'Inter',system-ui,sans-serif; color:#3b4252; }
h1,h2,h3 { color:#1f2430; font-weight:600; }
.stApp { background:#ffffff; }
section[data-testid="stSidebar"] { background:#f6f7f9; border-right:1px solid #e3e6ea; }
div.stButton > button[kind="primary"] {
  background:#4f6bed; color:#fff; border:none; border-radius:10px; font-weight:500; }
div.stButton > button[kind="secondary"] {
  background:#fff; color:#1f2430; border:1px solid #e3e6ea; border-radius:10px; }
.hl-phase { font-weight:600; color:#4f6bed; margin:4px 0 10px; }
.hl-console { background:#f6f7f9; border:1px solid #e3e6ea; border-radius:12px;
  padding:14px; max-height:460px; overflow-y:auto; }
.hl-line { display:flex; gap:10px; padding:5px 0; border-bottom:1px solid #edf0f3; font-size:14px; }
.hl-tag { flex:0 0 40px; color:#6b7280; font-size:12px; padding-top:2px; }
.hl-txt { color:#3b4252; }
.hl-code { background:#1f2430; color:#e6e8ec; border-radius:8px; padding:10px;
  font-family:ui-monospace,Menlo,monospace; font-size:12.5px; white-space:pre-wrap; margin:0; }
.hl-badge { display:inline-block; font-size:11px; padding:1px 8px; border-radius:999px;
  border:1px solid currentColor; margin-left:6px; }
</style>
"""


def page_setup() -> None:
    st.set_page_config(page_title="Hypo Loop", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)


def status_badge_html(status: str) -> str:
    color = STATUS_COLOR.get(status, MUTED)
    label = STATUS_LABEL.get(status, status)
    return f'<span class="hl-badge" style="color:{color}">{label}</span>'
```

- [ ] **Step 2: 확인** — Run: `python -c "import ui.theme as t; print(t.ACCENT, t.STATUS_LABEL['done']); print(callable(t.page_setup), callable(t.status_badge_html))"` → `#4f6bed 완료` / `True True`.

- [ ] **Step 3: Commit**
```bash
git add ui/theme.py
git commit -m "feat: calm theme tokens + CSS (no emoji)"
```

---

## Task 6: 대시보드 차트 (Plotly + 점 클릭)

**Files:**
- Create: `ui/dashboard_view.py`
- Test: `tests/test_dashboard_data.py`

- [ ] **Step 1: 테스트 작성** — `tests/test_dashboard_data.py`:
```python
from store.types import Hypothesis
from ui.dashboard_view import scores_to_figure_data


def _h(hid, content, status, score):
    return Hypothesis(hypothesis_id=hid, project_id="p", content=content,
                      max_experiments=2, parallel_count=1, status=status,
                      best_score=score)


def test_only_done_included():
    hs = [_h("h1", "가설1", "done", 0.8),
          _h("h2", "가설2", "registered", None),
          _h("h3", "가설3", "running", None)]
    data = scores_to_figure_data(hs)
    assert len(data) == 1
    assert data[0]["id"] == "h1"
    assert data[0]["score"] == 0.8
    assert "가설1" in data[0]["label"]


def test_empty_when_none_done():
    assert scores_to_figure_data([_h("h1", "x", "registered", None)]) == []
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_dashboard_data.py -q` → FAIL.

- [ ] **Step 3: 구현** — `ui/dashboard_view.py`:
```python
"""대시보드 — 가설별 최고 점수 차트(Plotly). 점 클릭 시 보고서로 이동."""
from __future__ import annotations

from typing import List

import plotly.graph_objects as go
import streamlit as st

from store.base import HypoStore
from store.types import Hypothesis


def scores_to_figure_data(hypotheses: List[Hypothesis]) -> List[dict]:
    """완료된 가설만 차트 데이터로 변환: [{id, label, score}]."""
    out = []
    for idx, h in enumerate(hypotheses, start=1):
        if h.status == "done" and h.best_score is not None:
            label = f"가설 {idx}: {h.content[:18]}" if h.content else f"가설 {idx}"
            out.append({"id": h.hypothesis_id, "label": label, "score": h.best_score})
    return out


def render(store: HypoStore) -> None:
    st.subheader("가설별 최고 점수")
    st.caption("점수는 0~1이며 높을수록 좋습니다. 점을 클릭하면 해당 가설 보고서가 열립니다.")

    data = scores_to_figure_data(store.list_hypotheses())
    if not data:
        st.info("완료된 가설이 없습니다. 왼쪽에서 새 가설을 추가하고 실행해 보세요.")
        return

    labels = [d["label"] for d in data]
    scores = [d["score"] for d in data]
    ids = [d["id"] for d in data]

    fig = go.Figure(go.Scatter(
        x=scores, y=labels, mode="markers",
        marker=dict(size=16, color="#4f6bed"),
        customdata=ids, hovertemplate="%{y}<br>점수 %{x}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(range=[0, 1], title="점수 (0~1)"),
        yaxis=dict(title=""),
        height=80 + 46 * len(data), margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="#ffffff",
    )

    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun",
                            key="score_chart")
    points = (event or {}).get("selection", {}).get("points", [])
    if points:
        clicked_id = points[0].get("customdata")
        if clicked_id:
            st.session_state.selected_hypothesis = clicked_id
            st.session_state.view = "report"
            st.rerun()
```

- [ ] **Step 4: 통과 확인** — Run: `python -m pytest tests/test_dashboard_data.py -q` → PASS (2 passed). 또한 `python -c "import ui.dashboard_view; print('ok')"` → ok.

- [ ] **Step 5: Commit**
```bash
git add ui/dashboard_view.py tests/test_dashboard_data.py
git commit -m "feat: dashboard score chart (plotly) with point-click to report"
```

---

## Task 7: 사이드바 · 가설 등록 · 보고서 렌더

**Files:**
- Create: `ui/sidebar.py`, `ui/hypothesis_register.py`, `ui/report_view.py`

순수 로직 없음(렌더). import 확인으로 검증, 화면은 Task 8에서.

- [ ] **Step 1: `ui/sidebar.py`**
```python
"""좌측 사이드바 — 프로젝트(고정) + 가설 목록 + 새 가설."""
from __future__ import annotations

import streamlit as st

from store.base import HypoStore
from ui import theme


def render(store: HypoStore) -> None:
    with st.sidebar:
        project = store.get_project()
        st.markdown(f"#### 프로젝트")
        st.markdown(f"**{project.name}**")
        st.divider()

        st.markdown("#### 가설")
        hyps = store.list_hypotheses()
        if not hyps:
            st.caption("아직 가설이 없습니다.")
        for idx, h in enumerate(hyps, start=1):
            label = f"가설 {idx}: {h.content[:16]}" if h.content else f"가설 {idx}"
            if st.button(label, key=f"hyp_{h.hypothesis_id}",
                         use_container_width=True):
                st.session_state.selected_hypothesis = h.hypothesis_id
                st.session_state.view = "report" if h.status == "done" else "register"
                st.rerun()
            st.markdown(theme.status_badge_html(h.status), unsafe_allow_html=True)

        st.divider()
        if st.button("+ 새 가설", type="primary", use_container_width=True):
            st.session_state.selected_hypothesis = None
            st.session_state.view = "register"
            st.rerun()
        if st.button("대시보드", use_container_width=True):
            st.session_state.view = "dashboard"
            st.rerun()
```

- [ ] **Step 2: `ui/hypothesis_register.py`**
```python
"""가설 등록 — 상단 라이브 에이전트 활동 + 하단 입력 폼."""
from __future__ import annotations

import streamlit as st

from store.base import HypoStore
from ui import theme
from ui.agent_status import AgentActivityState, render_console


def render(store: HypoStore) -> None:
    st.subheader("새 가설 등록")

    activity_box = st.container()       # 상단: 라이브 활동
    st.divider()

    with st.form("hyp_form"):
        content = st.text_area("가설 내용", height=120,
                               placeholder="예) 객실 등급(Pclass)이 생존에 큰 영향을 준다.")
        col1, col2 = st.columns(2)
        max_experiments = col1.number_input("최대 실험 횟수", min_value=1,
                                             max_value=20, value=3, step=1)
        parallel_count = col2.number_input("병렬 횟수", min_value=1,
                                            max_value=8, value=1, step=1)
        submitted = st.form_submit_button("실행", type="primary")

    if submitted:
        if not content.strip():
            st.error("가설 내용을 작성해주세요.")
            return
        h = store.create_hypothesis(content.strip(), int(max_experiments),
                                    int(parallel_count))
        state = AgentActivityState()
        with activity_box:
            st.markdown("##### 에이전트 진행 상황")
            progress = st.progress(0.0)
            console = st.empty()
            total = int(max_experiments)
            done = 0
            for ev in store.run(h.hypothesis_id):
                state.apply(ev)
                if ev.kind == "metric":
                    done += 1
                    progress.progress(min(done / total, 1.0))
                with console:
                    render_console(state)
            progress.progress(1.0)
        st.session_state.selected_hypothesis = h.hypothesis_id
        st.session_state.view = "report"
        st.rerun()
```

- [ ] **Step 3: `ui/report_view.py`**
```python
"""보고서 화면 — 최고 점수, 점수 추이, 분석 텍스트, 가설."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from store.base import HypoStore


def render(store: HypoStore) -> None:
    hid = st.session_state.get("selected_hypothesis")
    if not hid:
        st.info("표시할 가설이 없습니다.")
        return
    h = store.get_report(hid)

    st.subheader("분석 보고서")
    if h.status != "done":
        st.warning("아직 완료되지 않은 가설입니다.")
        return

    col1, col2 = st.columns([1, 2])
    col1.metric("최고 점수 (0~1)", h.best_score)
    with col2:
        if h.score_history:
            df = pd.DataFrame({"실험": list(range(1, len(h.score_history) + 1)),
                               "점수": h.score_history}).set_index("실험")
            st.line_chart(df)

    st.markdown(f"**가설**\n\n> {h.content}")
    st.markdown(f"**실험 결과 분석**\n\n{h.analysis_text}")

    if st.button("대시보드로"):
        st.session_state.view = "dashboard"
        st.rerun()
```

- [ ] **Step 4: import 확인**
Run: `python -c "import ui.sidebar, ui.hypothesis_register, ui.report_view; print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Commit**
```bash
git add ui/sidebar.py ui/hypothesis_register.py ui/report_view.py
git commit -m "feat: sidebar, hypothesis register (live), report views"
```

---

## Task 8: 앱 셸 + 라우팅 + E2E

**Files:**
- Modify/Create: `app.py`

- [ ] **Step 1: `app.py` 교체** (기존 단일플로우 app.py를 새 셸로 교체)
```python
"""Hypo Loop — Streamlit 진입점. 사이드바 + 대시보드/등록/보고서 라우팅."""
from __future__ import annotations

import streamlit as st

from store.mock import MockStore
from ui import theme, sidebar, dashboard_view, hypothesis_register, report_view


def get_store():
    """store 주입 지점. 세션에 1개 보관(나중에 BackendStore로 교체)."""
    if "store" not in st.session_state:
        st.session_state.store = MockStore()
    return st.session_state.store


def main() -> None:
    theme.page_setup()
    st.title("Hypo Loop")

    if "view" not in st.session_state:
        st.session_state.view = "dashboard"
        st.session_state.selected_hypothesis = None

    store = get_store()
    sidebar.render(store)

    view = st.session_state.view
    if view == "register":
        hypothesis_register.render(store)
    elif view == "report":
        report_view.render(store)
    else:
        dashboard_view.render(store)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 구문/임포트/테스트**
Run: `python -c "import ast; ast.parse(open('app.py').read()); import app; print('ok')"` → `ok`.
Run: `python -m pytest -q` → 전체 통과(store/agent/dashboard 테스트).

- [ ] **Step 3: 앱 실행 E2E** — `streamlit run app.py` (또는 launch.json) 후 확인:
- 좌측 사이드바: 프로젝트 "타이타닉 생존 예측" 고정, [+ 새 가설] 버튼
- [+ 새 가설] → 등록 화면: 하단 입력(가설/실험횟수/병렬) + [실행] → 상단에 라이브 활동(단계/툴/코드/점수)이 실시간으로 흐름 → 완료 시 보고서로 전환
- 보고서: 최고 점수 + 점수 추이 차트 + 분석 + 가설
- 사이드바에 가설이 목록으로 쌓이고 상태 배지 표시
- "대시보드" → 점수 차트에 완료 가설이 점으로 표시, **점 클릭 시 보고서 열림**
- 디자인: 이모지 없음, 차분한 색/둥근 모서리

(각 화면 스크린샷 캡처)

- [ ] **Step 4: Commit**
```bash
git add app.py
git commit -m "feat: assemble Hypo Loop app shell + routing"
```

---

## 자체 점검 결과

- **스펙 커버리지**: 데이터모델/store(Task2·3=§2), 셸+사이드바(Task7·8=§3), 대시보드 차트+클릭
  (Task6=§4), 등록+라이브(Task4·7=§5), 보고서(Task7=§6), 통합경계 get_store(Task8=§7), 디자인
  (Task5=§8), 테스트(Task2~6=§10). 트리거(§7)는 목 store 시뮬레이션으로 반영, 실제 백엔드 교체는
  store 교체 지점으로 명시.
- **플레이스홀더**: 없음(모든 코드·명령·기대출력 명시).
- **타입 일관성**: `Hypothesis`/`AgentEvent`(Task2) → `MockStore`(Task3) → `AgentActivityState`
  (Task4)·`scores_to_figure_data`(Task6) → 렌더(Task7)·`app.py`(Task8)에서 동일 필드·시그니처 사용.
  `HypoStore` Protocol 메서드(get_project/list_hypotheses/create_hypothesis/run/get_report/
  best_scores)가 MockStore·렌더·app 전반에서 일치. `st.session_state`: view/selected_hypothesis/
  store 키 일관.
- **주의**: 기존 단일플로우 파일(input_form, 기존 dashboard_logic 등)은 새 app.py에서 미사용.
  삭제는 본 계획 범위 밖(혼선 방지로 남겨두되, 새 구조가 기본). plotly on_select는 Streamlit
  1.56/plotly 5.9에서 동작(Task8 수동 확인).
