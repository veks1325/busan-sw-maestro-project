"""가설 상세 화면 — 실행 중이면 라이브 진행, 완료되면 보고서(.md 미리보기)."""
from __future__ import annotations

import streamlit as st

from src.api.base import HypoStore
from src.components.agent_status import AgentActivityState, render_console
from src.components import report_viewer


def _render_running(h) -> None:
    st.subheader("실행 중")
    st.caption("에이전트가 백그라운드에서 진행 중입니다. 이 화면을 떠나도 실행은 계속됩니다.")

    total = max(int(h.max_experiments), 1)
    done = len(h.score_history)
    ratio = min(done / total, 1.0)
    pct = int(ratio * 100)

    state = AgentActivityState()
    for ev in list(h.events):       # 백그라운드 스레드가 갱신 중 → 스냅샷으로 순회
        state.apply(ev)
    if state.lines:
        render_console(state)

    if st.button("대시보드로", key="run_to_dash"):
        st.session_state.view = "dashboard"
        st.rerun()

    # 하단: 진행도 바(완수율)
    st.divider()
    st.progress(ratio, text=f"진행률 {pct}%  ·  실험 {done}/{total} 완료")


def _render_report(h) -> None:
    st.subheader("분석 보고서")

    left, right = st.columns([3, 1])
    with left:
        if h.best_score is not None:
            st.caption(f"최고 점수 {h.best_score} (0~1)  ·  실험 {h.max_experiments}회")
    with right:
        fname = f"report_{h.hypothesis_id[:8]}.md"
        st.download_button("다운로드 (.md)", data=h.report_md or "",
                           file_name=fname, mime="text/markdown",
                           use_container_width=True)

    # 백엔드가 주는 보고서(.md) 미리보기: 목차 + 하단 스크롤 진행바
    report_viewer.render(h.report_md or "")

    if st.button("대시보드로", key="report_to_dash"):
        st.session_state.view = "dashboard"
        st.rerun()


def render(store: HypoStore) -> None:
    hid = st.session_state.get("selected_hypothesis")
    if not hid:
        st.info("표시할 가설이 없습니다.")
        return
    h = store.get_report(hid)

    if h.status == "done":
        _render_report(h)
    else:
        _render_running(h)
