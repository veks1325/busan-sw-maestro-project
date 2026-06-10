"""가설 등록 폼 — 제출 시 백그라운드 실행을 시작하고 즉시 진행 화면으로 이동.

실제 에이전트는 오래 걸릴 수 있으므로 보고서가 나올 때까지 기다리지 않는다.
제출 즉시 좌측 사이드바에 가설이 '동작중'(노란색)으로 나타나고, 사용자는
다른 가설을 보거나 다른 작업을 계속할 수 있다.
"""
from __future__ import annotations

import streamlit as st

from src.api.base import HypoStore


def render(store: HypoStore, project_id: str) -> None:
    st.subheader("새 가설 등록")
    st.caption("실행을 시작하면 백그라운드에서 진행됩니다. 완료를 기다리지 않고 다른 작업을 해도 됩니다.")

    with st.form("hyp_form"):
        content = st.text_area("가설 내용", height=120,
                               placeholder="예) 전체 품질(OverallQual)이 주택 가격에 큰 영향을 준다.")
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
        h = store.create_hypothesis(project_id, content.strip(),
                                    int(max_experiments), int(parallel_count))
        store.start_run(h.hypothesis_id)        # 논블로킹: 즉시 반환
        st.session_state.selected_hypothesis = h.hypothesis_id
        st.session_state.expanded_project = project_id   # 사이드바에 바로 보이도록
        st.session_state.view = "report"        # 진행/보고서 화면(실행 중이면 라이브)
        st.rerun()
