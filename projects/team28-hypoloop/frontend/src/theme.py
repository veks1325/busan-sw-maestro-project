"""차분한 디자인 토큰 + CSS 주입 (이모지 없음)."""
from __future__ import annotations

import streamlit as st

# 색상 토큰 — 부드러운 뉴트럴 + 단일 포인트(인디고)
INK = "#1f2430"
BODY = "#3b4252"
MUTED = "#6b7280"
CANVAS = "#ffffff"
SOFT = "#f6f7f9"
HAIRLINE = "#e3e6ea"
ACCENT = "#4f6bed"
ACCENT_SOFT = "#eef1fd"
SUCCESS = "#2f9e6e"
RUNNING = "#c08a2d"
ERROR = "#d64545"

# 상태 배지 색/라벨
STATUS_COLOR = {"registered": MUTED, "running": RUNNING, "done": SUCCESS,
                "error": ERROR}
STATUS_LABEL = {"registered": "등록됨", "running": "실행 중", "done": "완료",
                "error": "오류"}

# 사이드바 가설 버튼 우측 상태 점 색 (완료=초록 / 진행중=노랑 / 오류=빨강 / 등록=회색)
STATUS_DOT = {"registered": "#b0b6c0", "running": "#e0a700",
              "done": SUCCESS, "error": ERROR}


def status_dot_color(status: str) -> str:
    return STATUS_DOT.get(status, "#b0b6c0")

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family:'Inter',system-ui,sans-serif; color:#3b4252; }
h1,h2,h3 { color:#1f2430; font-weight:600; }
.stApp { background:#ffffff; }
section[data-testid="stSidebar"] { background:#f6f7f9; border-right:1px solid #e3e6ea; }
div.stButton > button[kind="primary"] {
  background:#4f6bed; color:#fff; border:none; border-radius:10px; font-weight:500; }
div.stButton > button[kind="secondary"] {
  background:#fff; color:#1f2430; border:1px solid #e3e6ea; border-radius:10px; }
.hl-phase { font-weight:600; color:#4f6bed; margin:4px 0 10px; }
.hl-console { background:#f6f7f9; border:1px solid #e3e6ea; border-radius:12px;
  padding:14px; max-height:460px; overflow-y:auto; }
.hl-line { display:flex; gap:10px; padding:5px 0; border-bottom:1px solid #edf0f3; font-size:14px; }
.hl-tag { flex:0 0 40px; color:#6b7280; font-size:12px; padding-top:2px; }
.hl-txt { color:#3b4252; }
.hl-code { background:#1f2430; color:#e6e8ec; border-radius:8px; padding:10px;
  font-family:ui-monospace,Menlo,monospace; font-size:12.5px; white-space:pre-wrap; margin:0; }
.hl-badge { display:inline-block; font-size:11px; padding:1px 8px; border-radius:999px;
  border:1px solid currentColor; margin-left:6px; }
.hl-brand { font-size:13px; font-weight:600; color:#4f6bed; letter-spacing:0.4px;
  margin:0 0 14px; }
.hl-proj-label { font-size:11px; color:#6b7280; text-transform:uppercase;
  letter-spacing:0.6px; margin-bottom:2px; }
.hl-proj-name { font-size:20px; font-weight:700; color:#1f2430; margin-bottom:2px; }
.hl-hyp-head { font-size:12px; color:#6b7280; font-weight:600; margin:6px 0 4px; }

/* ===== 사이드바 간격: 프로젝트끼리는 기본(넓게), 프로젝트-가설은 촘촘하게 ===== */
/* 가설 묶음 내부(가설들 + 새 가설)만 촘촘하게 */
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] [data-testid="stVerticalBlock"] { gap:0.3rem; }
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] [data-testid="stHorizontalBlock"] { gap:0.2rem; }
/* 가설 묶음을 프로젝트 버튼 바로 아래로 붙여 같은 그룹처럼 보이게 */
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] { margin-top:-0.55rem; }

/* ===== 사이드바 트리 버튼 (st-key 접두사로 구분) ===== */
/* 프로젝트: 크게 + 파란 배경 + 흰 글씨 */
section[data-testid="stSidebar"] div[class*="st-key-proj_"] button {
  background:#4f6bed !important; color:#fff !important; border:none !important;
  border-radius:10px; padding:0.72rem 0.9rem;
  box-shadow:0 1px 2px rgba(79,107,237,0.25); }
section[data-testid="stSidebar"] div[class*="st-key-proj_"] button:hover {
  background:#3f59d6 !important; color:#fff !important; }
section[data-testid="stSidebar"] div[class*="st-key-proj_"] button p {
  font-size:1.02rem !important; font-weight:700 !important; }

/* 가설: 흰색, 좌측 정렬, 한 줄(...), 우측에 상태 점 자리 */
section[data-testid="stSidebar"] div[class*="st-key-hyp_"] button {
  background:#fff !important; color:#3b4252 !important;
  border:1px solid #e3e6ea !important; border-radius:8px;
  position:relative; padding-right:1.9rem; overflow:hidden;
  justify-content:flex-start !important; }
section[data-testid="stSidebar"] div[class*="st-key-hyp_"] button:hover {
  border-color:#4f6bed !important; color:#3b4252 !important; }
section[data-testid="stSidebar"] div[class*="st-key-hyp_"] button > * {
  min-width:0; }
section[data-testid="stSidebar"] div[class*="st-key-hyp_"] button p {
  text-align:left; width:100%; min-width:0; font-weight:500;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* 펼침 애니메이션: 위에서 아래로 부드럽게 내려오기 */
@keyframes hl-slidedown {
  from { opacity:0; transform:translateY(-10px); }
  to   { opacity:1; transform:translateY(0); }
}
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] {
  animation: hl-slidedown 0.24s ease-out; }

/* 행 hover 시 우상단 X(삭제) 노출 */
section[data-testid="stSidebar"] div[class*="st-key-prow_"],
section[data-testid="stSidebar"] div[class*="st-key-hrow_"] { position:relative; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"],
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] {
  position:absolute; top:3px; right:4px; width:auto !important;
  opacity:0; transition:opacity .15s ease; z-index:6; }
section[data-testid="stSidebar"] div[class*="st-key-prow_"]:hover div[class*="st-key-pdel_"],
section[data-testid="stSidebar"] div[class*="st-key-hrow_"]:hover div[class*="st-key-hdel_"] {
  opacity:1; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button,
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button {
  background:transparent !important; border:none !important; box-shadow:none !important;
  padding:0 5px !important; min-height:0 !important; height:1.3rem; line-height:1;
  font-size:0.95rem; border-radius:6px; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button p {
  color:#ffffff !important; font-weight:700 !important; }
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button p {
  color:#9aa1ad !important; font-weight:700 !important; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button:hover p,
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button:hover p {
  color:#d64545 !important; }

/* 추가 버튼(새 가설/새 프로젝트): 파스텔 연파랑 */
section[data-testid="stSidebar"] div[class*="st-key-newhyp_"] button,
section[data-testid="stSidebar"] div[class*="st-key-new_proj"] button {
  background:#eaf0ff !important; color:#3f59d6 !important;
  border:1px dashed #b9c7f5 !important; border-radius:8px; font-weight:500; }
section[data-testid="stSidebar"] div[class*="st-key-newhyp_"] button:hover,
section[data-testid="stSidebar"] div[class*="st-key-new_proj"] button:hover {
  background:#dfe8ff !important; color:#3f59d6 !important; }
</style>
"""


def page_setup() -> None:
    st.set_page_config(page_title="Hypo Loop", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)


def status_badge_html(status: str) -> str:
    color = STATUS_COLOR.get(status, MUTED)
    label = STATUS_LABEL.get(status, status)
    return f'<span class="hl-badge" style="color:{color}">{label}</span>'
