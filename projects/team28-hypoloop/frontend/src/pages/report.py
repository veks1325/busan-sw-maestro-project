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

    # 1) 로그 콘솔(고정 높이)
    state = AgentActivityState()
    for ev in list(h.events):       # 백그라운드 스레드가 갱신 중 → 스냅샷으로 순회
        state.apply(ev)
    render_console(state)

    # 2) 로그 바로 아래: 진행률 바
    st.progress(ratio, text=f"진행률 {pct}%  ·  실험 {done}/{total} 완료")

    # 3) 최하단: 대시보드로
    st.divider()
    if st.button("대시보드로", key="run_to_dash"):
        st.session_state.view = "dashboard"
        st.rerun()


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

    # 보고서(.md) 미리보기: 목차 + 스크롤 진행바 + 경로의 img/ 이미지 병합
    report_viewer.render(h.report_md or "",
                         base_dir=getattr(h, "report_dir", ""))

    details = getattr(h, "experiment_reports", [])
    if details:
        st.divider()
        st.subheader("실험 상세 보고서")
        st.caption("각 실험에서 생성한 report.md와 시각화 이미지입니다.")

        for index, detail in enumerate(details, start=1):
            score_text = f" · 점수 {detail.score}" if detail.score is not None else ""
            label = f"실험 {index} · {detail.exp_id[:8]}{score_text}"
            with st.expander(label, expanded=index == 1):
                st.download_button(
                    "상세 보고서 다운로드 (.md)",
                    data=detail.report_md,
                    file_name=f"experiment_{detail.exp_id[:8]}.md",
                    mime="text/markdown",
                    key=f"detail_download_{detail.exp_id}",
                )
                report_viewer.render(
                    detail.report_md,
                    height=720,
                    base_dir=detail.report_dir,
                )

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
