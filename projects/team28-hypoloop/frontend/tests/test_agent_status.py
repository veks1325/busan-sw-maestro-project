from src.api.types import AgentEvent
from src.components.agent_status import AgentActivityState


def ev(kind="step", phase="EDA", text="t", score=None):
    return AgentEvent(phase=phase, kind=kind, text=text, score=score)


def test_apply_tracks_phase_and_lines():
    s = AgentActivityState()
    s.apply(ev(kind="step", phase="계획 수립", text="시작"))
    assert s.current_phase == "계획 수립"
    assert len(s.lines) == 1


def test_metric_collects_scores():
    s = AgentActivityState()
    s.apply(ev(kind="metric", text="점수", score=0.7))
    s.apply(ev(kind="metric", text="점수", score=0.8))
    assert s.scores == [0.7, 0.8]
    assert s.latest_score() == 0.8


def test_lines_capped():
    s = AgentActivityState(max_lines=5)
    for i in range(8):
        s.apply(ev(text=f"l{i}"))
    assert len(s.lines) == 5
    assert s.lines[0].text == "l3"


def test_latest_score_none_when_empty():
    assert AgentActivityState().latest_score() is None
