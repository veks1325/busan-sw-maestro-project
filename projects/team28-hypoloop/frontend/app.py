"""Hypo Loop — Streamlit 진입점. 사이드바 + 대시보드/등록/보고서 라우팅."""
from __future__ import annotations

import os
import time

import streamlit as st

from src.api.backend import BackendStore
from src.api.mock import MockStore
from src import theme
from src.components import sidebar
from src.pages import (dashboard, hypothesis_register, report, project_setup,
                       home)


def get_store():
    """Use the real backend by default; opt into the mock with HYPOLOOP_STORE."""
    use_mock = os.getenv("HYPOLOOP_STORE", "backend").lower() == "mock"
    current = st.session_state.get("store")
    needs_replacement = current is None or (
        use_mock and not isinstance(current, MockStore)
    ) or (
        not use_mock and not isinstance(current, BackendStore)
    )
    if needs_replacement:
        if use_mock:
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
        st.session_state.view = "home"
        st.session_state.selected_hypothesis = None

    store = get_store()

    sidebar.render(store)

    view = st.session_state.view

    # 새 프로젝트 설정 화면(학습/실험 데이터 + 설명 업로드)
    if view == "project_setup" and st.session_state.get("setup_project"):
        project_setup.render(store, st.session_state.setup_project)
        if _any_running(store):
            _heartbeat()
        return

    project_id = st.session_state.get("selected_project")

    # 랜딩(프로젝트 선택) 화면
    if view == "home" or project_id is None:
        home.render(store)
        if _any_running(store):
            _heartbeat()
        return

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
