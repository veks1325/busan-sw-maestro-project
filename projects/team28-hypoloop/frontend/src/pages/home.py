"""랜딩 화면 — 선택된 프로젝트가 없을 때(시작/저장 후) 안내."""
from __future__ import annotations

import streamlit as st

from src.api.base import HypoStore


def render(store: HypoStore) -> None:
    has_projects = bool(store.list_projects())
    if has_projects:
        title = "프로젝트를 선택해주세요"
        sub = "왼쪽에서 프로젝트를 선택하거나 [+ 새 프로젝트]로 새로 만드세요."
    else:
        title = "새 프로젝트로 시작하세요"
        sub = "왼쪽의 [+ 새 프로젝트]를 눌러 데이터를 올리고 시작하세요."
    st.markdown(
        f'<div class="hl-home"><div class="t">{title}</div>'
        f'<div class="s">{sub}</div></div>',
        unsafe_allow_html=True)
