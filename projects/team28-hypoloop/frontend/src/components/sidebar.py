"""좌측 사이드바 — 프로젝트 목록(+추가/이름변경/삭제) 트리.

동작:
    - 프로젝트 버튼을 누르면 그 아래 가설이 펼쳐진다(슬라이드 다운). 한 번 더 누르면 접힌다.
    - 펼친 상태에서만 가설 목록 + [+ 새 가설]이 보인다.
    - [+ 새 프로젝트]를 누르면 새 프로젝트가 생기고 이름을 바로 편집할 수 있다.
    - 프로젝트/가설 항목에 마우스를 올리면 우상단 X가 떠서 삭제할 수 있다.

스타일(색/크기/한 줄 말줄임/애니메이션/X 노출)은 theme.py의 st-key 접두사 CSS가 담당한다.
가설 우측 상태 점 색만 상태별로 동적 주입한다(완료=초록/진행중=노랑/오류=빨강).
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
    """가설 버튼 우측(::after)에 상태 표시를 올리는 CSS를 주입한다.

    - 진행중: 주황색 원형 진행도(파이) — 대략적인 완료율을 채워서 표시
    - 완료: 초록 원 / 오류: 빨강 원 / 등록됨: 회색 원
    """
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


def _commit_rename(store: HypoStore, project_id: str, key: str) -> None:
    """이름 입력 변경 시(Enter/포커스 해제) 호출 — 값이 있으면 적용하고 편집 종료."""
    val = (st.session_state.get(key) or "").strip()
    if val:
        store.rename_project(project_id, val)
    st.session_state.editing_project = None


def _open_project(project_id: str) -> None:
    """프로젝트 선택 + 펼침/접힘 토글(편집 상태 해제)."""
    st.session_state.editing_project = None
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
    if st.session_state.get("editing_project") == project_id:
        st.session_state.editing_project = None
    st.session_state.selected_hypothesis = None
    st.session_state.view = "dashboard"


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

        editing = st.session_state.get("editing_project")
        expanded = st.session_state.get("expanded_project")

        for p in store.list_projects():
            with st.container(key=f"prow_{p.project_id}"):
                if editing == p.project_id:
                    key = f"rename_{p.project_id}"
                    st.text_input(
                        "프로젝트 이름", value=p.name, key=key,
                        label_visibility="collapsed", placeholder="프로젝트 이름",
                        on_change=_commit_rename, args=(store, p.project_id, key),
                    )
                else:
                    if st.button(p.name, key=f"proj_{p.project_id}",
                                 use_container_width=True):
                        _open_project(p.project_id)
                        st.rerun()
                    if st.button("×", key=f"pdel_{p.project_id}",
                                 help="프로젝트 삭제"):
                        _delete_project(store, p.project_id)
                        st.rerun()

            # 펼친 프로젝트만 하위 가설 표시(슬라이드 다운 애니메이션)
            if expanded == p.project_id:
                with st.container(key=f"hypbox_{p.project_id}"):
                    _, body = st.columns([1, 14])
                    with body:
                        hyps = store.list_hypotheses(p.project_id)
                        _inject_status_dots(hyps)
                        for h in hyps:
                            with st.container(key=f"hrow_{h.hypothesis_id}"):
                                label = _truncate(h.content) or "가설"
                                if st.button(label, key=f"hyp_{h.hypothesis_id}",
                                             use_container_width=True):
                                    st.session_state.editing_project = None
                                    st.session_state.selected_hypothesis = h.hypothesis_id
                                    st.session_state.view = "report"
                                    st.rerun()
                                if st.button("×", key=f"hdel_{h.hypothesis_id}",
                                             help="가설 삭제"):
                                    _delete_hypothesis(store, h.hypothesis_id)
                                    st.rerun()
                        if st.button("+ 새 가설", key=f"newhyp_{p.project_id}",
                                     use_container_width=True):
                            st.session_state.editing_project = None
                            st.session_state.selected_hypothesis = None
                            st.session_state.view = "register"
                            st.rerun()

        if st.button("+ 새 프로젝트", key="new_proj", use_container_width=True):
            new = store.create_project(
                f"프로젝트 {len(store.list_projects()) + 1}")
            st.session_state.selected_project = new.project_id
            st.session_state.expanded_project = new.project_id
            st.session_state.editing_project = new.project_id   # 이름 즉시 편집
            st.session_state.selected_hypothesis = None
            st.session_state.view = "dashboard"
            st.rerun()
