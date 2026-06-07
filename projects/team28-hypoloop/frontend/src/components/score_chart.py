"""ScoreChart — 가설별 최고 점수 그래프(Plotly).

완료된 가설을 X축에 균등 분포로 찍고(1개=가운데, 2개=1/3·2/3 …),
Y축은 0~1 평가 점수의 고정 ㄴ자 프레임. 점을 클릭하면 해당 가설 id를 돌려준다.
"""
from __future__ import annotations

from typing import List, Optional

import plotly.graph_objects as go
import streamlit as st

from src.api.types import Hypothesis


def scores_to_figure_data(hypotheses: List[Hypothesis]) -> List[dict]:
    """완료된 가설만 차트 데이터로 변환: [{id, index, label, score}].

    index = 전체 가설 중 1-based 번호(X축 라벨), score = 0~1 평가점수(Y축).
    """
    out = []
    for idx, h in enumerate(hypotheses, start=1):
        if h.status == "done" and h.best_score is not None:
            label = f"가설 {idx}: {h.content[:18]}" if h.content else f"가설 {idx}"
            out.append({"id": h.hypothesis_id, "index": idx,
                        "label": label, "score": h.best_score})
    return out


def build_figure(data: List[dict]) -> go.Figure:
    """차트 데이터를 고정 프레임 산점도 Figure로 변환."""
    n = len(data)
    xs = [(i + 1) / (n + 1) for i in range(n)]   # 균등 분포 위치
    ys = [d["score"] for d in data]
    ids = [d["id"] for d in data]
    hovers = [d["label"] for d in data]
    ticktext = [str(d["index"]) for d in data]

    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="markers",
        marker=dict(size=18, color="#4f6bed"),
        customdata=ids, hovertext=hovers,
        hovertemplate="%{hovertext}<br>점수 %{y}<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(title="가설 번호", range=[0, 1], tickvals=xs, ticktext=ticktext,
                   showline=True, linecolor="#3b4252", zeroline=False,
                   gridcolor="#eef1f4"),
        yaxis=dict(title="평가 점수 (0~1)", range=[0, 1], dtick=0.2,
                   showline=True, linecolor="#3b4252", zeroline=False,
                   gridcolor="#eef1f4"),
        height=460, margin=dict(l=50, r=20, t=10, b=45),
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
    )
    return fig


def render(data: List[dict], key: str = "score_chart") -> Optional[str]:
    """차트를 렌더하고, 점이 클릭되면 그 가설 id를 반환(없으면 None)."""
    fig = build_figure(data)
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun",
                            key=key)
    points = (event or {}).get("selection", {}).get("points", [])
    if points:
        return points[0].get("customdata")
    return None
