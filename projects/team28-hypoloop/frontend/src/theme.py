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
  padding:14px; height:420px; overflow-y:auto; }
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
/* 설정 화면 상단 팝업 공지 — 위에서 내려왔다가 3초 후 다시 올라감 */
.hl-toast-wrap { position:fixed; top:0; left:0; right:0; z-index:99999;
  display:flex; justify-content:center; pointer-events:none; }
.hl-toast2 { position:relative; top:-160px; opacity:0;
  display:flex; align-items:center; justify-content:center; gap:8px;
  background:#ffffff; border:1.5px solid #4f6bed; color:#1f2430;
  padding:13px 44px; border-radius:12px; box-shadow:0 8px 22px rgba(0,0,0,0.16);
  font-size:1.05rem; font-weight:700; line-height:1.35; text-align:center;
  white-space:nowrap; animation:hl-drop 2.3s ease-in-out forwards; }
.hl-toast2 svg { flex:0 0 auto; }
@keyframes hl-drop {
  0%   { top:-160px; opacity:0; }   /* 화면 위(숨김) */
  18%  { top:72px;   opacity:1; }   /* 내려옴(상단 툴바 아래로, ~0.4s) */
  82%  { top:72px;   opacity:1; }   /* 약 1.5초 유지 */
  100% { top:-160px; opacity:0; }   /* 다시 올라감(~0.4s) */
}
/* 랜딩(프로젝트 선택) 페이지 — 상하/좌우 중앙 */
.hl-home { display:flex; flex-direction:column; justify-content:center;
  align-items:center; text-align:center; color:#6b7280; min-height:74vh; }
.hl-home .t { font-size:2rem; font-weight:700; color:#1f2430; margin-bottom:10px; }
.hl-home .s { font-size:0.95rem; }

/* ===== 사이드바 간격: 프로젝트끼리는 기본(넓게), 프로젝트-가설은 촘촘하게 ===== */
/* 가설 묶음 내부(가설들 + 새 가설)만 촘촘하게 */
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] [data-testid="stVerticalBlock"] { gap:0.3rem; }
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] [data-testid="stHorizontalBlock"] { gap:0.2rem; }
/* 가설 묶음을 프로젝트 버튼 바로 아래로 붙여 같은 그룹처럼 보이게 */
section[data-testid="stSidebar"] div[class*="st-key-hypbox_"] { margin-top:-0.55rem; }

/* ===== 사이드바 프로젝트 버튼: 공통 크기 + 상태별 색 ===== */
section[data-testid="stSidebar"] div[class*="st-key-projready_"] button,
section[data-testid="stSidebar"] div[class*="st-key-projwarn_"] button,
section[data-testid="stSidebar"] div[class*="st-key-projcfg_"] button {
  border:none !important; border-radius:10px; padding:0.72rem 0.9rem;
  box-shadow:0 1px 2px rgba(0,0,0,0.08); }
section[data-testid="stSidebar"] div[class*="st-key-projready_"] button p,
section[data-testid="stSidebar"] div[class*="st-key-projwarn_"] button p,
section[data-testid="stSidebar"] div[class*="st-key-projcfg_"] button p {
  font-size:1.02rem !important; font-weight:700 !important; }
/* 준비 완료 = 파랑 */
section[data-testid="stSidebar"] div[class*="st-key-projready_"] button {
  background:#4f6bed !important; color:#fff !important; }
section[data-testid="stSidebar"] div[class*="st-key-projready_"] button:hover {
  background:#3f59d6 !important; color:#fff !important; }
/* 미완료 = 주황 */
section[data-testid="stSidebar"] div[class*="st-key-projwarn_"] button {
  background:#e0922e !important; color:#fff !important; }
section[data-testid="stSidebar"] div[class*="st-key-projwarn_"] button:hover {
  background:#cf831f !important; color:#fff !important; }
/* 설정 중 = 회색 */
section[data-testid="stSidebar"] div[class*="st-key-projcfg_"] button {
  background:#c4c9d2 !important; color:#3b4252 !important; }
section[data-testid="stSidebar"] div[class*="st-key-projcfg_"] button:hover {
  background:#b6bcc7 !important; color:#3b4252 !important; }

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

/* ===== 우상단 원형 X 삭제: 행 hover 시 노출, X에 hover 시 빨강 ===== */
section[data-testid="stSidebar"] div[class*="st-key-prow_"],
section[data-testid="stSidebar"] div[class*="st-key-hrow_"] { position:relative; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"],
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] {
  position:absolute; top:-7px; right:-7px; width:auto !important; z-index:7;
  opacity:0; transition:opacity .15s ease; }
section[data-testid="stSidebar"] div[class*="st-key-prow_"]:hover div[class*="st-key-pdel_"],
section[data-testid="stSidebar"] div[class*="st-key-hrow_"]:hover div[class*="st-key-hdel_"] {
  opacity:1; }
/* 원 안의 X */
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button,
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button {
  width:22px !important; height:22px !important; min-height:0 !important;
  padding:0 !important; border-radius:50% !important;
  background:#ffffff !important; border:1px solid #d7dbe2 !important;
  box-shadow:0 1px 3px rgba(0,0,0,0.18) !important;
  display:flex; align-items:center; justify-content:center; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button p,
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button p {
  color:#8a909c !important; font-weight:700 !important; font-size:0.78rem !important;
  line-height:1 !important; }
/* X에 hover 시 빨강 */
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button:hover,
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button:hover {
  background:#d64545 !important; border-color:#d64545 !important; }
section[data-testid="stSidebar"] div[class*="st-key-pdel_"] button:hover p,
section[data-testid="stSidebar"] div[class*="st-key-hdel_"] button:hover p {
  color:#ffffff !important; }

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
