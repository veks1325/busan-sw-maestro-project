# Hypo Loop — Frontend (Streamlit)

ML 자동화 에이전트의 프론트엔드. 프로젝트/가설 관리, 가설별 최고 점수 대시보드,
가설 등록 + 에이전트 진행 상황, 보고서 화면을 제공한다.

백엔드/에이전트는 별도 파트가 담당하며, 프론트는 `src/api`의 `HypoStore` 계약을
통해 데이터에 접근한다. 현재는 `MockStore`(메모리 + 시뮬레이션)로 동작하고,
이후 실제 백엔드 API 클라이언트로 교체한다.

## 구조

```
frontend/
├── app.py                      # Streamlit 진입점 (라우팅: 대시보드/등록/보고서)
├── requirements.txt
├── .streamlit/config.toml      # 라이트 테마 설정
└── src/
    ├── theme.py                # 공통 디자인 토큰 + CSS
    ├── pages/
    │   ├── dashboard.py        # Dashboard — 가설별 최고 점수
    │   ├── hypothesis_register.py  # HypothesisRegister — 가설 등록(논블로킹 실행)
    │   └── report.py           # Report — 실행 중 진행 / 완료 보고서
    ├── components/
    │   ├── score_chart.py      # ScoreChart — 가설별 점수 그래프
    │   ├── agent_status.py     # AgentStatus — 에이전트 동작 콘솔
    │   └── sidebar.py          # 프로젝트/가설 트리(추가·이름변경·삭제)
    └── api/                    # 백엔드 연동 계층(현재 Mock)
        ├── base.py             # HypoStore 계약(Protocol)
        ├── mock.py             # MockStore
        └── types.py            # Project / Hypothesis / AgentEvent
```

## 실행

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## 테스트

```bash
cd frontend
pytest -q
```

## 주요 동작

- **다중 프로젝트**: 좌측에서 프로젝트 추가/이름변경/삭제, 클릭 시 하위 가설 펼침.
- **비동기 실행**: 가설 등록 시 백그라운드로 실행 시작(논블로킹). 완료를 기다릴
  필요 없이 다른 작업 가능. 사이드바에 진행중(주황 원형 진행도)/완료(초록)/오류(빨강) 표시.
- **대시보드**: 가설별 최고 점수를 점으로 표시, 점 클릭 시 보고서로 이동.
- **보고서**: 최고 점수, 점수 추이, 분석 텍스트.

## 백엔드 연동(이후)

`src/api/base.py`의 `HypoStore` 계약을 그대로 구현하는 `ApiStore`를 추가하고
`app.py`의 `get_store()`에서 교체하면 된다. 화면 코드는 수정할 필요가 없다.
