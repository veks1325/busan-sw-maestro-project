from src.api.types import Project, Hypothesis, AgentEvent


def test_hypothesis_defaults():
    h = Hypothesis(hypothesis_id="h1", project_id="p1", content="가설",
                   max_experiments=3, parallel_count=1)
    assert h.status == "registered"
    assert h.best_score is None
    assert h.score_history == []


def test_agent_event_fields():
    ev = AgentEvent(phase="EDA", kind="metric", text="점수", score=0.8)
    assert ev.kind == "metric" and ev.score == 0.8


def test_project_fields():
    p = Project(project_id="p1", name="타이타닉")
    assert p.name == "타이타닉"


from src.api.mock import MockStore
from src.api.base import HypoStore


def _pid(s):
    return s.list_projects()[0].project_id


def test_mockstore_satisfies_protocol():
    assert isinstance(MockStore(), HypoStore)


def test_default_project_exists():
    s = MockStore()
    assert len(s.list_projects()) == 1
    assert s.list_projects()[0].name == "타이타닉 생존 예측"


def test_create_project():
    s = MockStore()
    p = s.create_project("프로젝트 2")
    assert p.name == "프로젝트 2"
    assert len(s.list_projects()) == 2


def test_rename_project():
    s = MockStore()
    p = s.create_project("프로젝트 2")
    s.rename_project(p.project_id, "타이타닉 2차")
    assert s.list_projects()[-1].name == "타이타닉 2차"


def test_rename_project_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        MockStore().rename_project("nope", "x")


def test_delete_project_removes_project_and_its_hypotheses():
    s = MockStore()
    p1 = _pid(s)
    p2 = s.create_project("p2").project_id
    s.create_hypothesis(p1, "a", 2, 1)
    s.create_hypothesis(p2, "b", 2, 1)
    s.delete_project(p1)
    ids = [p.project_id for p in s.list_projects()]
    assert p1 not in ids and p2 in ids
    assert s.list_hypotheses(p1) == []
    assert len(s.list_hypotheses(p2)) == 1


def test_delete_hypothesis():
    s = MockStore()
    pid = _pid(s)
    h = s.create_hypothesis(pid, "a", 2, 1)
    s.create_hypothesis(pid, "b", 2, 1)
    s.delete_hypothesis(h.hypothesis_id)
    remaining = [x.hypothesis_id for x in s.list_hypotheses(pid)]
    assert h.hypothesis_id not in remaining
    assert len(remaining) == 1


def test_create_and_list():
    s = MockStore()
    pid = _pid(s)
    assert s.list_hypotheses(pid) == []
    h = s.create_hypothesis(pid, "Pclass 영향", max_experiments=3, parallel_count=1)
    assert h.status == "registered"
    assert h.project_id == pid
    assert len(s.list_hypotheses(pid)) == 1


def test_hypotheses_scoped_by_project():
    s = MockStore()
    p1 = _pid(s)
    p2 = s.create_project("p2").project_id
    s.create_hypothesis(p1, "a", 2, 1)
    s.create_hypothesis(p2, "b", 2, 1)
    assert len(s.list_hypotheses(p1)) == 1
    assert len(s.list_hypotheses(p2)) == 1


def test_run_emits_events_and_completes():
    s = MockStore(step_delay=0.0)
    h = s.create_hypothesis(_pid(s), "가설", max_experiments=3, parallel_count=1)
    events = list(s.run(h.hypothesis_id))
    assert len(events) > 0
    kinds = {e.kind for e in events}
    assert "step" in kinds and "metric" in kinds
    done = s.get_report(h.hypothesis_id)
    assert done.status == "done"
    assert done.best_score is not None and 0.0 <= done.best_score <= 1.0
    assert len(done.score_history) == 3
    assert done.report_md.startswith("#")


def test_start_run_is_nonblocking_and_completes():
    s = MockStore(step_delay=0.0)
    h = s.create_hypothesis(_pid(s), "가설", max_experiments=3, parallel_count=1)
    s.start_run(h.hypothesis_id)        # 즉시 반환(논블로킹)
    s._threads[h.hypothesis_id].join(timeout=5)
    done = s.get_report(h.hypothesis_id)
    assert done.status == "done"
    assert len(done.score_history) == 3
    assert len(done.events) > 0


def test_best_scores_only_done():
    s = MockStore(step_delay=0.0)
    pid = _pid(s)
    h1 = s.create_hypothesis(pid, "a", 2, 1)
    s.create_hypothesis(pid, "b", 2, 1)
    list(s.run(h1.hypothesis_id))
    bs = s.best_scores(pid)
    assert len(bs) == 1
    assert bs[0][0].hypothesis_id == h1.hypothesis_id
    assert bs[0][1] == s.get_report(h1.hypothesis_id).best_score


def test_get_report_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        MockStore().get_report("nope")
