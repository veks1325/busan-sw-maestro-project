"""Hypo Loop — Streamlit 진입점. 사이드바 + 대시보드/등록/보고서 라우팅."""
from __future__ import annotations

import os
import time

import streamlit as st

from src.api.backend import BackendStore
from src.api.mock import MockStore
from src import theme
from src.components import sidebar
from src.pages import dashboard, hypothesis_register, report


def get_store():
    """store 주입 지점. 세션에 1개 보관.

    HYPOLOOP_STORE=mock 이면 MockStore(데모 시뮬레이션), 그 외에는
    실제 백엔드(FastAPI)와 통신하는 BackendStore를 사용한다.
    """
    if "store" not in st.session_state:
        if os.getenv("HYPOLOOP_STORE", "backend") == "mock":
            st.session_state.store = MockStore()
        else:
            st.session_state.store = BackendStore()
    return st.session_state.store


def _any_running(store) -> bool:
    """진행 중(running)인 가설이 하나라도 있는지."""
    for p in store.list_projects():
        for h in store.list_hypotheses(p.project_id):
            if h.status == "running":
                return True
    return False


@st.fragment(run_every=1.0)
def _heartbeat() -> None:
    """실행 중일 때만 렌더 — 약 1초마다 앱 전체를 새로고침해 상태(노란→초록) 갱신.

    스로틀: 마지막 새로고침 후 ~1초가 지났을 때만 rerun(초기 렌더에서의 즉시 폭주 방지).
    """
    last = st.session_state.get("_hb_last", 0.0)
    now = time.monotonic()
    if now - last >= 0.95:
        st.session_state._hb_last = now
        st.rerun(scope="app")


def main() -> None:
    theme.page_setup()

    if "view" not in st.session_state:
        st.session_state.view = "dashboard"
        st.session_state.selected_hypothesis = None

    store = get_store()
    # 기본 선택 프로젝트(첫 프로젝트). 프로젝트가 없으면 None.
    if not st.session_state.get("selected_project"):
        projects = store.list_projects()
        st.session_state.selected_project = (
            projects[0].project_id if projects else None)

    sidebar.render(store)

    project_id = st.session_state.selected_project
    if project_id is None:
        st.info("왼쪽에서 새 프로젝트를 추가해 시작하세요.")
        return

    view = st.session_state.view
    if view == "register":
        hypothesis_register.render(store, project_id)
    elif view == "report":
        report.render(store)
    else:
        dashboard.render(store, project_id)

    # 실행 중인 가설이 있으면 주기적으로 새로고침해 상태(노란색→초록색)를 갱신
    if _any_running(store):
        _heartbeat()


if __name__ == "__main__":
    main()
