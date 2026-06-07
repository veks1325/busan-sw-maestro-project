from src.api.types import Hypothesis
from src.components.score_chart import scores_to_figure_data


def _h(hid, content, status, score):
    return Hypothesis(hypothesis_id=hid, project_id="p", content=content,
                      max_experiments=2, parallel_count=1, status=status,
                      best_score=score)


def test_only_done_included():
    hs = [_h("h1", "가설1", "done", 0.8),
          _h("h2", "가설2", "registered", None),
          _h("h3", "가설3", "running", None)]
    data = scores_to_figure_data(hs)
    assert len(data) == 1
    assert data[0]["id"] == "h1"
    assert data[0]["index"] == 1
    assert data[0]["score"] == 0.8
    assert "가설1" in data[0]["label"]


def test_empty_when_none_done():
    assert scores_to_figure_data([_h("h1", "x", "registered", None)]) == []
