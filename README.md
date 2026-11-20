# 🎭 커튼콜 플래너 (CurtainCall Planner)

**“내 시간 · 예산 · 귀가 조건에 맞는 공연과 회차”를 찾아 관람 계획으로 만들어 주는 LangGraph Agent**

> “11월 21일 토요일 저녁 6시 이후 대학로에서 연극 보고, 밤 11시 반까지 망원역 도착해야 해. 5만원 이하로.”
> → 공연 목록 → 상세(러닝타임·회차·가격) → 공연장 좌표 → 집 좌표 → 대중교통 시간 → 회차별 판정 → 날씨 → 응답

예매 사이트는 **작품 중심**으로 검색되지만, 실제 고민은 **조건 중심**입니다(끝나면 몇 시? 집에 제때 가나? 5만원 안쪽?).
LLM만으로는 지금 상연 중인 회차·가격을 모르고, API 한 번으로는 러닝타임·가격이 없어 여러 Tool을 이어 호출해야 합니다.

## 화면

| 대화 | 내 관람 계획 | 실행 로그 |
|---|---|---|
| 추천 카드(회차 → 종료 → 귀가 도착, 최저가, 판정 근거, 날씨), 제외 사유, 실행 과정 타임라인(재계획 강조), 처리 중·키 누락 안내 | 날짜별 목록, 시간 겹침 표시, 인라인 수정·삭제 즉시 반영 | 세션별 이벤트 타임라인(원본 JSON), 삭제만 가능 |

백엔드 없이 예시 화면 보기: `frontend/index.html?demo` (저장된 실제 API 샘플을 실제 Agent 그래프로 돌린 결과, `scripts/make_demo_data.py`)

## 실행 방법

```bash
python3.11 -m venv .venv                                  # Python 3.10+
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cp .env.example .env                                      # 키 값을 직접 채운다 (아래 '키 발급')
.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

- 화면: http://127.0.0.1:8000 · API 문서: http://127.0.0.1:8000/docs
- 테스트: `.venv/bin/python -m pytest` — 271개, 네트워크 없이 저장된 샘플·LLM 대역으로 실행

| 스크립트 | 용도 | 외부 호출 |
|---|---|---|
| `scripts/check_keys.py [--live]` | 키 설정 여부(boolean) / 4개 API 1회씩 확인 | 0 / 4 |
| `scripts/check_llm.py` | LLM 연결 확인: 짧은 질문 · bind_tools · 구조화 출력 | LLM 3~4 |
| `scripts/collect_samples.py` | 실제 응답을 키 제거 후 `backend/samples/`에 저장 (있으면 건너뜀) | ~65 |
| `scripts/check_tools_live.py` | Tool 5개 실제 호출 1회씩 | ~6 |
| `scripts/run_scenarios.py` | **검증 시나리오 S1~S11을 실제 LLM + 실제 API로 실행** → `docs/verification.md`, `docs/logs/` | LLM ~32, API ~200 |
| `scripts/run_scenarios_without_llm.py` | 요청 분석만 고정값으로 넣고 나머지를 실제 API로 실행 (LLM을 쓸 수 없을 때) | ~95 |
| `scripts/scan_secrets.py [--all]` | 커밋 전 키 검사 (값은 출력하지 않음) | 0 |

## 기능

### 필수 (F3001~F3019)

| 영역 | 구현 |
|---|---|
| Tool (F3001~F3004) | 외부 API Tool 5개를 레지스트리에 등록, Agent에는 이름·설명(“언제 쓰는지”)·입력 스키마만 전달. 공통 응답 `{"ok", "data"/"error", "meta"}`, 예외를 밖으로 던지지 않음, 실패 원인 코드(detail) 기록 |
| 분석·계획 (F3005~F3006) | analyze(LLM 구조화 출력, 언급된 조건만 추출 → 코드로 검증·병합), plan(첫 계획만 LLM `bind_tools` → 규칙 검증 → 의존 순서 보완, 실패 시 규칙 템플릿) |
| 실행·판정 (F3007~F3008) | 후보 상세 병렬 조회, 2단계 판정(시간·예산 1차 통과 후보만 공연장 좌표·대중교통 조회), C1~C7 순수 함수, 회차를 모르면 역산 기준 |
| 재계획 (F3009) | R1 후보 확장 → R2 지역 → R3 장르, 최대 3회, 사용자 제약(날짜·시각·예산)은 자동 변경 금지, 상한 도달 시 탈락 통계 + 계산된 조정안 |
| Memory (F3010) | `MemorySaver(thread_id=session_id)`: 조건·직전 추천·최근 대화. “같은 날 뮤지컬로” → 장르만 변경 |
| 응답 (F3011) | 숫자는 템플릿이 출력, LLM은 요약 1~2문장(요약에 결과에 없는 숫자가 있으면 템플릿으로 대체), 근거·제외 사유·가정·출처 |
| 로깅 (F3012~F3014) | EventBus 발행·구독(발행자는 구독자를 모름 — import 관계를 테스트로 검사), 로깅 Agent는 LLM 미사용·추가만, 조회·삭제 API(수정 API 없음) |
| 계획 (F3015~F3016) | 겹쳐도 저장하고 겹침 목록 반환(`[start, end)`), 수정·삭제 즉시 반영 |
| 서버·화면 (F3017~F3019) | FastAPI + Pydantic, 전역 오류 처리(스택 트레이스·키 미노출), 순수 HTML/CSS/JS, 실행 과정·재계획 지점·처리 중·키 누락 안내 |

### 심화 — F3021 Planner·Worker (`AGENT_MODE`, 기본 C)

- **Planner**: LLM이 고른 Tool을 검증·보완해 작업 목록으로 만든다. 각 작업에 `fixed`(Worker가 못 바꾸는 인자: 날짜·지역·장르)와 `repairable`(사용자가 자유롭게 쓴 글: 집 위치·작품명)을 표시
- **Worker**: 정상 경로는 규칙으로 실행(LLM 0회). `NO_RESULT`·`INVALID_INPUT`이고 고칠 인자가 있을 때만 LLM이 재시도·건너뜀·재계획 요청을 고름(최대 2회). 고정 인자 변경·원문과 겹치지 않는 값은 코드가 거부
- **비교 실험** (`docs/experiment.md`, 실제 LLM·API, 12개 시나리오 × 3회):

| 구성 | 성공률 | 평균 재계획 | 요청당 LLM | 평균 응답(초) | Tool 호출 |
|---|---|---|---|---|---|
| A 단일 Agent | 81% | 0.92 | 2.22 | 5.4 | 25.1 |
| B Worker LLM 끔 | 100% | 0.33 | 2.17 | 5.3 | 15.4 |
| C Worker LLM 켬 | 100% | 0.33 | 2.56 | 5.8 | 17.2 |

정상 경로(S1~S9)는 세 구성이 같고(Worker LLM 0회), 집 위치를 카카오가 못 찾는 W1~W3에서 A는 헛된 재계획 끝에 실패(22%), B는 되묻기, C는 표기를 고쳐 추가 질문 없이 해결(W1·W2)하고 추측이 필요한 W3는 되묻는다.

## 구조

```text
backend/app/
  main.py · config.py · llm.py(get_llm: LLM 객체는 여기서만) · offline.py(샘플·LLM 대역 실행기)
  api/ (chat · plans · logs · health)   schemas/models.py
  agent/ state · graph · deps · service · constraints(C1~C7) · relax(재계획 사다리) · prompts · llm_steps
         nodes/ (understand · planning · execution · respond · common)
  tools/ base(공통 응답·레지스트리·HTTP·캐시) · kopis · kakao · kma · kma_grid · parsers · region_alias · redact
  events/ (bus · types)   logging_agent/subscriber.py   db/ (database · plans_repo · logs_repo)
backend/tests/ · backend/samples/(키 제거된 실제 응답) · frontend/ · docs/ · scripts/
```

Agent 그래프: `docs/agent_graph.mmd` (`graph.get_graph().draw_mermaid()` 출력)

## LLM

- 모델 **`claude-haiku-5-5`** — SSAFY GMS의 Anthropic 중계 경로를 `langchain-openai`의 `ChatOpenAI`(OpenAI 호환 호출)로 부른다.
  처음에는 `gpt-4.1-mini`(GMS OpenAI 경로)였으나 GMS 상위 OpenAI 조직의 지출 한도(HTTP 429)로 강사 안내에 따라 바꿨다. 코드는 두 경로를 모두 지원한다.
- LLM은 **세 곳에서만**: analyze(구조화 출력) · plan(`bind_tools`) · respond(요약). 일반 요청 LLM 3회.
- 이 모델은 `temperature`를 받지 않는다(HTTP 400) → 보내지 않고, 일관성은 코드 검증(형식·계획 규칙·요약 숫자 대조)이 맡는다.

## 키 발급 · 설정 요약

`.env`에 직접 넣습니다(커밋 금지, `.gitignore` 등록). `.env.example`에는 이름만 있습니다.

| 변수 | 발급처 · 값 |
|---|---|
| `KOPIS_API_KEY` | KOPIS → 고객센터 → OPEN API → 인증키 발급신청 (회원가입 불필요) |
| `KAKAO_REST_API_KEY` | 카카오디벨로퍼스 앱 → REST API 키, [카카오맵] 사용 설정 ON |
| `KMA_SERVICE_KEY` | 공공데이터포털 “기상청 단기예보 조회서비스” 활용신청 → **Decoding 키** |
| `GMS_KEY` | SSAFY GMS 키 |
| `LLM_BASE_URL` | `https://gms.ssafy.io/gmsapi/api.anthropic.com/v1` |
| `LLM_MODEL` | `claude-haiku-5-5` |

`LLM_BASE_URL`이 비었거나 https가 아니거나 host가 제공사(`*.openai.com`, `*.anthropic.com`)이면 LLM을 호출하지 않습니다(GMS 키가 제공사로 직접 전송되지 않게).

## 외부 API 출처 · 이용조건

| API | 출처 표시 · 조건 | 한도 |
|---|---|---|
| KOPIS 공연예술통합전산망 | `출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr)` 표시 의무 | 비공개 → 캐시·샘플·요청 조절로 절약 |
| 카카오맵 (로컬·대중교통) | 카카오맵 | 키워드 10만/일, 대중교통 1,000/일 |
| 기상청 단기예보 | 공공누리 제1유형(출처표시) | 개발계정 10,000/일 |

## 검증 결과 (`docs/verification.md`)

실제 LLM(GMS) + 실제 외부 API로 S1~S11 실행 — **12개 중 11개 기대 동작 충족**.
유일한 차이는 S2 원래 문장이 실제 데이터에서 1차에 바로 통과해 재계획이 일어나지 않은 것(데이터 의존). 예산만 바꾼 S2′에서 1차 통과 0 → R1 → 통과를 확인.
S1 전체 실행 로그 `docs/logs/S1.jsonl`, 재계획 사례 `docs/logs/S2b.jsonl`·`S3.jsonl`.

| 시나리오 | 결과 |
|---|---|
| S1 대표 요청 | 추천 5편, 재계획 0, LLM 3회 (1위 18:00→19:15→망원역 20:03, 30,000원) |
| S2′ 재계획 후 통과 | 1차 0편 → R1(남은 후보 10편) → 1편 통과 |
| S3 상한 도달 | 재계획 3회 후 중단, “탈락 38편: 시작 시각 이전 37 · 그 요일 공연 없음 1”, 계산된 조정안 |
| S4 기상청 키 없음 | 추천 정상, 날씨만 ‘확인 불가’ + 설정 안내 |
| S5 / S8 | Tool 0회 (간단 응답 / 집 위치 되묻기) |
| S6 Memory | 날짜·시각·예산·귀가 조건 유지, 장르만 뮤지컬로 |
| S7 / S11 | 사실 조회(검색 → 상세, 판정 없음) / 날씨만 조회(장소 → 날씨) |
| S9 / S10 | 저장 + 겹침 안내 / 예보 범위 밖 → 기상청 호출 0회 |

## 트러블슈팅 (실행하며 찾은 문제와 해결)

| 문제 | 원인 | 해결 |
|---|---|---|
| LLM 계획이 매번 규칙 템플릿으로 대체됨 | Claude는 `bind_tools`에서 지금 바로 실행할 수 있는 첫 단계 Tool만 고름 | LLM은 “필요한 Tool”을 결정하고, 코드는 조건과 대조해 검증한 뒤 의존 순서대로 뒤 단계를 채우도록 재설계 → 대체 0건 |
| 공연 상세 일부가 약 20ms 만에 연속 실패 | KOPIS 방화벽이 몰린 요청을 400 “Request Blocked”로 차단(실패 원인 코드 `detail`로 확정) | 재시도 전 대기, 차단 시 1회 재시도, KOPIS 요청 조절(동시 4·간격 0.15초) |
| “토요일 밤 대학로 비 와?”가 경북 구미의 날씨로 답함 | 카카오에 ‘대학로’만 검색하면 구미의 ‘대학로’, ‘서울 대학로’는 경기 시흥의 ‘서울대학로’가 1위 | 지역 별칭으로 구까지 알아내 ‘서울 종로구 대학로’로 검색하고, 결과도 그 구 안에서만 고름 |
| LLM 호출이 모두 HTTP 400 | `claude-haiku-5-5`는 temperature를 받지 않음 | Anthropic 경로에서는 temperature를 보내지 않음 |
| 강사 안내 코드(`default_headers`)로 키가 객체 repr에 노출 | pydantic 필드로 저장되어 출력됨 | `x-api-key`를 HTTP 클라이언트 헤더로 옮김(요청은 동일) — 테스트로 고정 |
| 테스트가 설계 위반을 잡음 | 오프라인 실행기가 `app/agent` 안에서 로깅 모듈을 import | 조립 코드는 `app/offline.py`로 이동(Agent는 로깅 모듈을 모름) |

## 핵심 설계 결정 (면접용)

| 질문 | 답 |
|---|---|
| LLM을 어디에 썼나 | 의도 분석·첫 계획·요약 3곳만. 판정·재계획·겹침·로깅은 순수 함수 → 재현성과 비용 확보 |
| LLM에게 Tool 선택을 어떻게 맡겼나 | LLM은 필요한 Tool을 고르고, 코드는 조건과 대조해 검증(귀가 조건이 없는데 이동시간을 고르면 거부)한 뒤 의존 순서로 보완 |
| 환각은 어떻게 막았나 | 확인 불가 값은 ‘판정 불가’ + 역산 기준, 숫자는 템플릿 출력, 요약의 숫자를 결과와 대조, 가격을 일부만 해석하면 최저가를 내지 않음, 위치를 못 찾으면 지어내지 않고 ‘찾지 못함’ |
| 재계획이 무한 반복되지 않나 | 상한 3회 + 사다리 소진 시 종료 + 키 없음처럼 다시 해도 같은 실패는 재계획 제외 |
| 로깅을 왜 분리했나 | 발행자는 구독자를 모름 → 로깅 장애가 대화에 영향 없음, 로그는 수정 불가 |
| 외부 API 호출을 어떻게 아꼈나 | 2단계 판정(1차 통과 후보만 좌표·대중교통), 좌표 지연 조회, 시설·경로·예보 캐시, 예보 범위 밖이면 기상청 미호출 |
| 느린 외부 API를 어떻게 다뤘나 | 측정으로 병목(KOPIS 처리량 초당 약 1.5건)을 확인 → 호출 수 감소 + LLM 계획 대기 시간에 후보 선반입 + 요청 조절 |

## 현재 상태 · 한계

- 필수 F3001~F3019 + 심화 F3021 구현, 테스트 271개 통과, 실제 LLM·API 시나리오 11/12 충족, 키 노출 검사 0건
- **응답 시간은 KOPIS 상태에 따라 달라진다**: 재계획 없는 S1이 11.3~15.1초인 실행도, 20.6초인 실행도 있었다(KOPIS 상세 1건 1.2~5.4초). 자체 목표(15초/재계획 포함 30초)를 KOPIS가 느릴 때는 넘는다
- 장르는 공통코드로 확인한 연극·뮤지컬·클래식만, 지역 구 단위는 서울만, 공휴일(HOL) 회차는 판정에 쓰지 않음, 기상청 격자 변환은 서울·부산 2곳만 대조(활용가이드 엑셀 대조 미완)
