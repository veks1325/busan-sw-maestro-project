# 라이브 에이전트 대시보드 — 설계서

작성일: 2026-06-04
담당: 정의찬 (UI / 프론트)
프로젝트: 28조 ML 자동화 에이전트 (hypoloop)

## 1. 목적

프론트에서 **AI(에이전트)가 실제로 돌아가는 모습을 실시간으로 보여준다.** 현재
"실행 중" 화면은 단계별 로그만 흐른다. 이를 **통합 대시보드**로 업그레이드한다:

- **에이전트 콘솔** — LLM(Solar) 호출, 생성된 코드, 단계별 로그를 실시간 피드로
- **지표 패널** — 루프별 성능 지표가 실시간 갱신되는 카드 + 라인차트
- **단계 스테퍼** — 계획수립 → EDA → 베이스라인 → 피처 → 튜닝 → 리포트 진행 표시

데이터는 **인프로세스 스트림**으로 받는다(추가 인프라 없음). 백엔드를 같은 프로세스에서
호출하고, 풍부해진 이벤트 스트림을 순회하며 렌더한다.

### 범위 밖

- 별도 HTTP/모니터링 엔드포인트, 외부 대시보드(MLflow UI) 임베드 — 이번 범위 아님
- 실제 에이전트(LangGraph + Solar) 구현 — 백엔드 영역. 본 작업은 **UI + 이벤트 계약**까지

## 2. 핵심 — 이벤트 스트림 확장 (계약)

현재 계약을 **하위호환**으로 확장한다. `backend/interface.py`:

```python
@dataclass
class ProgressEvent:
    stage: str
    loop_index: int
    status: str                          # "running" | "done" | "failed"
    message: str
    kind: str = "stage"                  # "stage"|"llm"|"code"|"log"|"metric"
    detail: str = ""                     # 생성 코드 / LLM 출력 / 로그 본문
    metric: Optional[MetricRecord] = None # kind=="metric"일 때 실시간 지표 1건
```

- 새 필드는 모두 **기본값**이 있어 기존 코드·백엔드 구현·테스트가 깨지지 않는다.
- 대시보드는 `kind`로 렌더를 분기한다.
- `kind` 의미:
  - `stage`: 단계 진행(기존 동작). 스테퍼/상태 갱신.
  - `llm`: LLM(Solar) 호출 1건. `detail`에 프롬프트 요지/응답 요약.
  - `code`: 에이전트가 생성/실행한 코드. `detail`에 코드 본문.
  - `log`: 일반 로그 한 줄. `detail` 또는 `message`.
  - `metric`: 지표 1건. `metric` 필드로 전달 → 지표 패널 실시간 갱신.

> 계약 변경은 백엔드 팀과 공유할 파일이다. 하위호환이라 즉시 영향은 없고, 백엔드가
> 준비되면 같은 형식으로 풍부한 이벤트를 emit하면 된다.

## 3. 컴포넌트 (각 파일 하나의 책임)

```
backend/interface.py          # ProgressEvent에 kind/detail/metric 추가
ui/dashboard_view.py          # ★ 신규 — 라이브 대시보드(실행 중 화면)
ui/dashboard_logic.py         # ★ 신규 — 순수 로직(이벤트 분류·집계). 단위 테스트 대상
backend/mock.py               # 단계마다 llm/code/log/metric 이벤트도 emit
backend/data_layer_backend.py # (통합 브랜치) 동일하게 풍부한 이벤트 emit
app.py                        # "running" 뷰에서 progress_view → dashboard_view 사용
```

- `ui/dashboard_view.py`: Streamlit 렌더. 좌(콘솔) + 우(지표) 2단 레이아웃 + 상단 스테퍼.
  런타임 의존이라 단위 테스트 대신, 렌더가 호출하는 **순수 로직은 분리**한다.
- `ui/dashboard_logic.py`: 순수 함수 — 이벤트를 콘솔 항목/지표/단계상태로 분류·누적하는
  `DashboardState`(또는 함수들). 단위 테스트로 검증.
- 기존 `progress_view.py`는 남겨두되(폴백/단순 모드), 기본 실행 흐름은 dashboard_view.

## 4. 데이터 흐름

```
app.py("running")
  → dashboard_view.render(backend, inp)
      state = DashboardState()
      for ev in backend.run(inp):          # 인프로세스 스트림
          state.apply(ev)                  # 순수 로직: kind별 분류·누적
          ─ stage  → 스테퍼/현재 단계 갱신
          ─ llm/code/log → 콘솔 피드에 누적(최근 N개 표시)
          ─ metric → 지표 카드 + 라인차트 실시간 갱신
      return backend.get_result()
  → 결과 화면(report_viewer)로 전환
```

## 5. 레이아웃 (Streamlit)

- 상단: 단계 스테퍼(계획수립→…→리포트) + 현재 루프 / 전체 루프 진행률
- 좌측 컬럼(넓게): **에이전트 콘솔** — 시간순 피드. 아이콘으로 종류 구분
  (🧠 LLM · 💻 코드(접을 수 있는 code 블록) · · 로그). 최근 N개 + 자동 스크롤 느낌.
- 우측 컬럼: **지표 패널** — 최신 지표 `st.metric`(Δ 강조) + 루프별 라인차트(베이스라인 vs 값)
- 하단: 실행 중 안내(취소/대기) — 완료 시 결과 화면으로 자동 전환

## 6. 지금 보이는 내용 (정직성)

실제 에이전트가 아직 없으므로, **콘솔의 LLM 호출·생성 코드는 시뮬레이션(데모)** 이다.
mock/adapter가 단계에 맞춰 그럴듯한 llm/code/log 이벤트를 생성한다. 단, **데이터 적재·
지표는 실제 백엔드(hypoloop)** 를 사용한다(통합 브랜치). 진짜 에이전트가 붙으면 콘솔도
실제 내용으로 대체된다. 대시보드에 "데모(시뮬레이션) 활동" 표식을 둔다.

## 7. 테스트

- **단위(순수 로직)**: `dashboard_logic` — 이벤트 분류, 콘솔 누적(최근 N 제한), 지표 집계,
  단계 상태 전이, 빈 스트림/실패 이벤트 처리.
- **계약**: ProgressEvent 새 필드 기본값/형태.
- **백엔드 emit**: mock/adapter가 kind별 이벤트를 실제로 흘리는지(스트림에 llm/code/metric
  포함) 검증.
- **라이브 렌더**: Streamlit으로 수동 확인(스크린샷).

## 8. 제약 / 원칙

- 인프로세스 스트림 특성상 긴 작업 중 UI가 묶일 수 있음 — 데모 규모에선 허용.
- 콘솔 피드는 **최근 N개 + 요약**으로 제한해 메모리/렌더 폭증 방지(N=30).
- 새 필드는 하위호환 유지(백엔드 비파괴).

## 9. 비주얼 디자인 (Airtable 디자인 시스템 적용)

제공된 Airtable 디자인 시스템의 **토큰과 원칙**을 Streamlit 앱 전체 테마와 대시보드에
적용한다. 마케팅 전용 컴포넌트(top-nav, hero-band, pricing, footer, logo-strip,
article-card, rainbow-stripe)는 우리 제품(대시보드)에 해당 없음 → **범위 밖**. 적용
대상은 다음 파운데이션이다.

### 9.1 디자인 토큰 → `ui/theme.py`

기존 `theme.py`의 색/헬퍼를 디자인 시스템 토큰으로 교체·확장하고, 공통 CSS를 주입한다.

- **색상**: primary/ink `#181d26`, primary-active `#0d1218`, canvas `#ffffff`,
  surface-soft `#f8fafc`, surface-strong `#e0e2e6`, surface-dark `#181d26`,
  hairline `#dddddd`, body `#333840`, muted `#41454d`, link `#1b61c9`,
  success `#006400`, info `#254fad`.
  시그니처 surface: coral `#aa2d00`, forest `#0a2e0e`, cream `#f5e9d4`,
  peach `#fcab79`, mint `#a8d8c4`, yellow `#f4d35e`, mustard `#d9a441`.
- **타이포**: Haas 미보유 → **Inter / Inter Tight**(오픈소스 대체)를 웹폰트로 로드.
  display 40/400, section 32/400, title 24/400, label 16/500, button 16/500,
  body 14/400, caption 14/500. **디스플레이는 굵게(700) 금지** — 강조는 크기·색·
  시그니처 surface로(원칙).
- **간격**: 4px 베이스. 섹션 리듬 96px(대시보드에선 밴드 상하 여백에 적용),
  카드 패딩 시그니처 48 / 콘텐츠 24~32, 거터 24/16.
- **라운드**: primary CTA·시그니처 카드 `12px`, 콘텐츠/지표 카드 `10px`,
  입력 `6px`, 아이콘/아바타 `full`. **pill은 프라이싱 전용 → 사용 안 함**.
- **elevation**: 색면 우선, 그림자 최소. 시그니처 surface는 무그림자·색 대비로 깊이.

### 9.2 버튼

- **primary**: 배경 near-black `#181d26`, 흰 텍스트, 12px 라운드, 패딩 16×24.
  뷰포트당 하나(희소성). 예: "새 분석 시작".
- **secondary**: 흰 배경 + 헤어라인 아웃라인 + ink 텍스트, 12px 라운드.
- Streamlit `st.button(type="primary"/"secondary")`에 CSS로 위 스타일을 매핑.

### 9.3 대시보드에 시그니처 surface 적용

- **현재 단계 배너**: 활성 단계를 시그니처 surface로 강조 — 베이스라인/튜닝 등
  voltage 모먼트에 coral/forest/dark 카드 사용(과하지 않게 한 곳).
- **에이전트 콘솔**: canvas/surface-soft 카드 + 헤어라인. `code` 항목은 surface-dark
  블록에 흰 텍스트(코드 가독). LLM/log 항목은 아이콘 + body 텍스트.
- **지표 패널**: 지표 카드는 cream/surface-soft surface, 10px 라운드.
  `st.metric`(Δ 강조) + 라인차트.
- 색면 리듬: 흰 캔버스 사이에 시그니처 카드가 punctuate. 같은 surface 연속 금지.

### 9.3.1 적용 범위

대시보드뿐 아니라 입력 폼·진행/결과 화면도 같은 테마(폰트·색·버튼·라운드)를 공유한다
(`theme.page_setup()`에서 CSS 1회 주입). 단, 신규 비주얼의 핵심은 대시보드 화면.

### 9.4 제약

- Streamlit 내부 컴포넌트는 스타일 제어가 제한적 → CSS 주입으로 **근사**한다(완전 동일 X).
- 폰트는 웹폰트 로드 실패 시 system-ui 폴백(디자인 문서 폴백 지침과 동일).
- 마케팅 전용 컴포넌트·hover 상태는 구현하지 않음(no-hover 정책 준수).
