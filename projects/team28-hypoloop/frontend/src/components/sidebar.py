"""좌측 사이드바 — 프로젝트 목록(+추가/설정/삭제) 트리.

동작:
    - [+ 새 프로젝트]를 누르면 빈 프로젝트를 만들고 오른쪽에 "새 프로젝트 설정" 화면을 연다.
      (사이드바의 그 프로젝트 박스는 설정 중을 뜻하는 회색으로 표시)
    - 프로젝트 버튼 색: 준비 완료(데이터+설명)=파랑 / 미완료=주황 / 설정 중=회색
    - 준비된 프로젝트를 누르면 가설이 펼쳐진다(토글). 미완료 프로젝트를 누르면 설정 화면으로 돌아간다.
    - 프로젝트/가설 항목에 마우스를 올리면 왼쪽으로 밀리며 오른쪽에서 삭제 버튼이 나타난다.

스타일(색/크기/슬라이드 삭제/애니메이션)은 theme.py의 st-key 접두사 CSS가 담당한다.
가설 우측 상태 점 색만 상태별로 동적 주입한다(진행중=주황 파이/완료=초록/오류=빨강).
"""
from __future__ import annotations

import streamlit as st

from src.api.base import HypoStore
from src import theme

_MAX_LEN = 18   # 가설 내용 표시 최대 길이(초과 시 ...). CSS가 한 줄을 추가 보장.


def _truncate(text: str, n: int = _MAX_LEN) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + "..."


def _inject_status_dots(hyps) -> None:
    """가설 버튼 우측(::after)에 상태 표시를 올리는 CSS를 주입한다."""
    parts = []
    for h in hyps:
        sel = (f'section[data-testid="stSidebar"] '
               f'div.st-key-hyp_{h.hypothesis_id} button::after')
        base = ('content:"";position:absolute;right:9px;top:50%;'
                'transform:translateY(-50%);width:13px;height:13px;'
                'border-radius:50%;box-sizing:border-box;'
                'box-shadow:0 0 0 1px rgba(0,0,0,0.06) inset;')
        if h.status == "running":
            total = max(int(h.max_experiments), 1)
            pct = int(min(len(h.score_history) / total, 1.0) * 100)
            bg = f'background:conic-gradient(#e0a700 {pct}%, #f3e3b8 {pct}%);'
        elif h.status == "done":
            bg = f'background:{theme.SUCCESS};'
        elif h.status == "error":
            bg = f'background:{theme.ERROR};'
        else:
            bg = 'background:#c4c9d2;'
        parts.append(f'{sel}{{{base}{bg}}}')
    if parts:
        st.markdown("<style>" + "".join(parts) + "</style>",
                    unsafe_allow_html=True)


def _open_setup(project_id: str) -> None:
    st.session_state.setup_project = project_id
    st.session_state.selected_project = project_id
    st.session_state.expanded_project = None
    st.session_state.selected_hypothesis = None
    st.session_state.show_notice = False      # 진입 시 경고 안 뜨게
    st.session_state.view = "project_setup"


def _open_ready(project_id: str) -> None:
    """준비된 프로젝트 선택 + 펼침/접힘 토글."""
    st.session_state.setup_project = None
    st.session_state.selected_project = project_id
    st.session_state.selected_hypothesis = None
    st.session_state.view = "dashboard"
    cur = st.session_state.get("expanded_project")
    st.session_state.expanded_project = None if cur == project_id else project_id


def _delete_project(store: HypoStore, project_id: str) -> None:
    store.delete_project(project_id)
    if st.session_state.get("selected_project") == project_id:
        remaining = store.list_projects()
        st.session_state.selected_project = (
            remaining[0].project_id if remaining else None)
    if st.session_state.get("expanded_project") == project_id:
        st.session_state.expanded_project = None
    if st.session_state.get("setup_project") == project_id:
        st.session_state.setup_project = None
        st.session_state.view = "dashboard"
    st.session_state.selected_hypothesis = None


def _delete_hypothesis(store: HypoStore, hypothesis_id: str) -> None:
    store.delete_hypothesis(hypothesis_id)
    if st.session_state.get("selected_hypothesis") == hypothesis_id:
        st.session_state.selected_hypothesis = None
        if st.session_state.get("view") in ("report", "register"):
            st.session_state.view = "dashboard"


def render(store: HypoStore) -> None:
    with st.sidebar:
        st.markdown('<div class="hl-brand">Hypo Loop</div>',
                    unsafe_allow_html=True)

        setup_pid = st.session_state.get("setup_project")
        expanded = st.session_state.get("expanded_project")

        for idx, p in enumerate(store.list_projects(), start=1):
            label = p.name or f"프로젝트{idx}"
            configuring = (setup_pid == p.project_id)
            if configuring:
                prefix = "projcfg"      # 회색(설정 중)
            elif p.is_ready:
                prefix = "projready"    # 파랑(준비 완료)
            else:
                prefix = "projwarn"     # 주황(미완료)

            with st.container(key=f"prow_{p.project_id}"):
                if st.button(label, key=f"{prefix}_{p.project_id}",
                             use_container_width=True):
                    if p.is_ready and not configuring:
                        _open_ready(p.project_id)
                    else:
                        _open_setup(p.project_id)
                    st.rerun()
                if st.button("×", key=f"pdel_{p.project_id}",
                             help="프로젝트 삭제"):
                    _delete_project(store, p.project_id)
                    st.rerun()

            # 준비된 프로젝트를 펼쳤을 때만 하위 가설 표시
            if p.is_ready and expanded == p.project_id:
                with st.container(key=f"hypbox_{p.project_id}"):
                    _, body = st.columns([1, 14])
                    with body:
                        hyps = store.list_hypotheses(p.project_id)
                        _inject_status_dots(hyps)
                        for h in hyps:
                            with st.container(key=f"hrow_{h.hypothesis_id}"):
                                hlabel = _truncate(h.content) or "가설"
                                if st.button(hlabel, key=f"hyp_{h.hypothesis_id}",
                                             use_container_width=True):
                                    st.session_state.selected_hypothesis = h.hypothesis_id
                                    st.session_state.view = "report"
                                    st.rerun()
                                if st.button("×", key=f"hdel_{h.hypothesis_id}",
                                             help="가설 삭제"):
                                    _delete_hypothesis(store, h.hypothesis_id)
                                    st.rerun()
                        if st.button("+ 새 가설", key=f"newhyp_{p.project_id}",
                                     use_container_width=True):
                            st.session_state.selected_hypothesis = None
                            st.session_state.view = "register"
                            st.rerun()

        if st.button("+ 새 프로젝트", key="new_proj", use_container_width=True):
            new = store.create_project("")   # 이름은 설정 화면에서(미입력 시 자동)
            _open_setup(new.project_id)
            st.rerun()
