"""새 프로젝트 설정 화면 — 학습/실험 데이터(CSV) + 데이터 설명(TXT) 업로드.

- 프로젝트명: 선택(미입력 시 "프로젝트N"으로 자동 설정). N은 프로젝트 순번.
- 파일: 학습 데이터(train.csv) + 실험 데이터(test.csv) + 데이터 설명(txt). 셋 다 들어오면 준비 완료.
- 파일이 올라오면 즉시 저장되어 좌측 버튼 색(준비=파랑 / 미완료=주황 / 설정중=회색)에 반영된다.
- 미완료 프로젝트를 다시 누르면 이 화면으로 돌아오고 그동안 넣은 내용이 유지된다.
"""
from __future__ import annotations

import streamlit as st

from src.api.base import HypoStore

# 확성기 아이콘(인라인 SVG, 이모지 미사용)
_MEGAPHONE = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
    'stroke="#4f6bed" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="m3 11 18-5v12L3 14v-3z"></path>'
    '<path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"></path></svg>')


def _read_text(uploaded) -> str:
    return uploaded.getvalue().decode("utf-8", "ignore")


def _show_popup(nonce: int, message: str) -> None:
    """상단 팝업 공지 — CSS 애니메이션(내려옴→유지→올라감). nonce를 컨테이너 key로 줘
    누를 때마다 새로 마운트되어 한 번씩 재생된다."""
    with st.container(key=f"hltoast_{nonce}"):
        st.markdown(
            f'<div class="hl-toast-wrap"><div class="hl-toast2">{_MEGAPHONE}'
            f'<span>{message}</span></div></div>',
            unsafe_allow_html=True)


def render(store: HypoStore, project_id: str) -> None:
    p = store.get_project(project_id)
    ids = [pp.project_id for pp in store.list_projects()]
    idx = (ids.index(project_id) + 1) if project_id in ids else len(ids) + 1
    default_name = f"프로젝트{idx}"

    # 상단 팝업 공지 — '완료(미입력)'를 눌렀을 때만(show_notice). 진입 시엔 안 뜸.
    nonce = st.session_state.get("setup_notice_n", 0)
    if st.session_state.get("show_notice"):
        missing = []
        if not p.has_train:
            missing.append("학습 데이터")
        if not p.has_test:
            missing.append("실험 데이터")
        if not p.has_desc:
            missing.append("설명 파일")
        need = ", ".join(missing) if missing else "프로젝트 데이터"
        _show_popup(nonce, f"{need}을(를) 업로드해주세요")

    st.subheader("새 프로젝트")
    st.caption("학습 데이터(train.csv) · 실험 데이터(test.csv) · 데이터 설명(TXT)을 올려 "
               "프로젝트를 만드세요. Kaggle 데이터처럼 train/test CSV와 설명 파일을 함께 "
               "넣으면 됩니다. 프로젝트명은 선택입니다(미입력 시 자동 지정).")

    # 프로젝트명 (placeholder = 프로젝트N, 미입력 시 그대로 이름이 됨)
    name = st.text_input("프로젝트명", value=(p.name or ""),
                         placeholder=default_name, key=f"setupname_{project_id}")

    # 학습 데이터(train CSV)
    train_file = st.file_uploader("학습 데이터 파일 (CSV)", type=["csv"],
                                  key=f"setuptrain_{project_id}")
    if p.train_filename:
        st.caption(f"현재 학습 데이터: {p.train_filename}")

    # 실험 데이터(test CSV)
    test_file = st.file_uploader("실험 데이터 파일 (CSV)", type=["csv"],
                                 key=f"setuptest_{project_id}")
    if p.test_filename:
        st.caption(f"현재 실험 데이터: {p.test_filename}")

    # 데이터 설명(TXT)
    txt_file = st.file_uploader("데이터 설명 (TXT)", type=["txt"],
                                key=f"setuptxt_{project_id}")
    if p.desc_filename:
        st.caption(f"현재 설명: {p.desc_filename}")

    # 업로드되면 즉시 저장 → 사이드바 색 갱신을 위해 rerun
    changed = False
    if train_file is not None and train_file.name != p.train_filename:
        store.update_project(project_id, train_csv=_read_text(train_file),
                             train_filename=train_file.name)
        changed = True
    if test_file is not None and test_file.name != p.test_filename:
        store.update_project(project_id, test_csv=_read_text(test_file),
                             test_filename=test_file.name)
        changed = True
    if txt_file is not None and txt_file.name != p.desc_filename:
        store.update_project(project_id, description=_read_text(txt_file),
                             desc_filename=txt_file.name)
        changed = True
    if changed:
        st.rerun()

    st.divider()
    final_name = name.strip() or default_name
    c1, c2, c3 = st.columns([1, 1, 1])

    # 완료: 모두 입력됐을 때만 대시보드로. 아니면 상단 공지(재강조).
    if c1.button("완료", type="primary", use_container_width=True):
        store.update_project(project_id, name=final_name)
        if store.get_project(project_id).is_ready:
            st.session_state.setup_project = None
            st.session_state.selected_project = project_id
            st.session_state.expanded_project = None   # 완료해도 가설은 펼치지 않음
            st.session_state.view = "dashboard"
        else:
            # 미완료: 경고 팝업 표시(컨테이너 key용으로 nonce 단조 증가)
            st.session_state.setup_notice_n = nonce + 1
            st.session_state.show_notice = True
        st.rerun()

    # 저장: 미완성이라도 저장하고 "프로젝트를 선택해주세요" 화면으로(흰색).
    if c2.button("저장", type="secondary", use_container_width=True):
        store.update_project(project_id, name=final_name)
        st.session_state.setup_project = None
        st.session_state.selected_project = None
        st.session_state.view = "home"
        st.rerun()

    # 취소: 아무것도 안 넣었으면 정리하고 나간다.
    if c3.button("취소", type="tertiary", use_container_width=True):
        leftover = store.get_project(project_id)
        st.session_state.setup_project = None
        if leftover.is_empty:
            store.delete_project(project_id)
        st.session_state.selected_project = None
        st.session_state.view = "home"
        st.rerun()
