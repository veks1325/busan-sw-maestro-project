"""Dashboard — 접속 시 첫 화면. 가설별 최고 점수 차트(ScoreChart) 표시.

점을 클릭하면 해당 가설의 보고서로 이동한다.
"""
from __future__ import annotations

import streamlit as st

from src.api.base import HypoStore
from src.components import score_chart


def render(store: HypoStore, project_id: str) -> None:
    st.subheader("가설별 최고 점수")
    st.caption("점수는 0~1이며 높을수록 좋습니다. 점을 클릭하면 해당 가설 보고서가 열립니다.")

    hyps = store.list_hypotheses(project_id)
    data = score_chart.scores_to_figure_data(hyps)
    if not data:
        st.info("완료된 가설이 없습니다. 왼쪽에서 새 가설을 추가하고 실행해 보세요.")
        return

    clicked_id = score_chart.render(data, key="score_chart")
    if clicked_id:
        st.session_state.selected_hypothesis = clicked_id
        st.session_state.view = "report"
        st.rerun()
