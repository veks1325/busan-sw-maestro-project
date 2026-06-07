"""라이브 에이전트 활동 — 순수 상태(AgentActivityState) + Streamlit 콘솔 렌더."""
from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from typing import List, Optional

import streamlit as st

from src.api.types import AgentEvent

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
        st.markdown(
            f'<div class="hl-phase">현재 단계 · {_html.escape(state.current_phase)}</div>',
            unsafe_allow_html=True)
    st.markdown(console_html(state.lines), unsafe_allow_html=True)
