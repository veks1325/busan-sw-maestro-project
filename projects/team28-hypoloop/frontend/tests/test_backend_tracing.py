from src.api.backend import _new_progress_events, _new_score_events


def test_progress_events_track_each_parallel_experiment() -> None:
    seen_tasks: dict[str, str] = {}
    history = [
        {
            "exp_id": "exp-2",
            "current_task": "모델 학습 중",
            "last_updated": "2026-06-10T22:00:02",
        },
        {
            "exp_id": "exp-1",
            "current_task": "EDA 진행 중",
            "last_updated": "2026-06-10T22:00:01",
        },
    ]

    events = _new_progress_events(history, seen_tasks)

    assert [event.phase for event in events] == ["EDA", "학습/평가"]
    assert len(_new_progress_events(history, seen_tasks)) == 0


def test_scores_are_deduplicated_by_experiment_id() -> None:
    seen_score_exp_ids: set[str] = set()
    first = _new_score_events(
        [{"exp_id": "exp-2", "score": 0.8}],
        seen_score_exp_ids,
    )
    second = _new_score_events(
        [
            {"exp_id": "exp-1", "score": 0.7},
            {"exp_id": "exp-2", "score": 0.8},
        ],
        seen_score_exp_ids,
    )

    assert [event.score for event in first] == [0.8]
    assert [event.score for event in second] == [0.7]
