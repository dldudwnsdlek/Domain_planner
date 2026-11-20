# 검증 결과 — LLM 없이 실제 API로 실행 (요청 분석만 고정값)

- 실행 시각: 2026-11-20T09:09
- 실행 방법: `.venv/bin/python scripts/run_scenarios_without_llm.py`
- 범위: analyze(LLM) 결과를 고정값으로 넣고, plan(규칙 템플릿) · execute · judge · replan · enrich · respond를 실제 KOPIS·카카오·기상청 API로 실행했다. LLM 호출은 0회다(GMS 429로 사용 불가).
- S2·S4는 이 표에 없다: S2는 실제 데이터에서 1차에 통과해 재계획이 재현되지 않을 수 있고, S4(기상청 키 제거)는 `backend/tests/test_graph.py::test_s4_*`로 검증한다.

- **LLM 칸은 실제 LLM 호출이 아니라 분석 대역(고정값) 호출 수다.** 실제 LLM 호출은 0회다.
- S10의 `get_weather×1`은 Tool이 예보 범위를 먼저 검사해 `OUT_OF_RANGE`로 끝낸 것으로, 기상청 API 호출은 0회다.

| ID | 요청 | 기대 동작 | 실제 동작 | 재계획 | LLM(대역) | Tool 호출 | 시간(ms) |
|---|---|---|---|---|---|---|---|
| S1 | 11월 21일 토요일 저녁 6시 이후 대학로에서 연극 보고, 밤 11시 반까지 망원역 도착해야 해. 5만원 이하로. | 통과 ≥ 1, 재계획 0 | status=ok · 추천 5편 (1위 아일랜드 18:00→19:15→도착 20:03, 30,000원, 날씨 ok) · Tool: search_performances×1, get_performance_detail×10, search_places×1, get_transit_time×5, get_weather×5 | 0 | 1 | 22 | 8613 |
| S3 | 토요일 밤 10시 이후 시작하는 뮤지컬, 2만원 이하 | 재계획 3회 후 중단 + 탈락 원인 통계 + 조정안 | status=limit_reached · 조정안: 시작 시각을 16:00 이후로 당기면 1편이 가능해요. · 응답: 조건에 맞는 공연을 찾지 못했어요 (재계획 3회). 탈락 40편: 시작 시각 이전 39 · 그 요일 공연 없음 1 조건을 바꿔 볼까요? · Tool: search_performances×2, get_performance_detail×40 | 3 | 1 | 42 | 23007 |
| S5 | 안녕! 이거 어떻게 써? | 계획 생략, Tool 0회 | status=ok · Tool: 0회 | 0 | 1 | 0 | 2 |
| S6 | 같은 날 뮤지컬로 바꿔줘 | 날짜·시각·예산 유지, 장르만 변경 | status=ok · 추천 2편 (1위 붓다, 세상의 길을 묻다 [대학로] 18:30→20:10→도착 20:57, 50,000원, 날씨 ok) · Tool: search_performances×1, get_performance_detail×10, get_transit_time×2, get_weather×2 | 0 | 1 | 15 | 1640 |
| S7 | '아일랜드' 러닝타임이랑 관람등급 알려줘 | 검색 → 상세 → 사실 응답 (판정 없음) | status=ok · facts: 아일랜드 75분 15세 이상 · Tool: search_performances×1, get_performance_detail×1 | 0 | 1 | 2 | 916 |
| S8 | 토요일에 연극 보고 집에 11시 반까지 가야 해 | Tool 호출 전 되묻기 | status=clarify · 응답: 귀가 시간을 계산하려면 집(또는 도착할 곳) 위치가 필요해요. 어디로 가시나요? (예: 망원역) · Tool: 0회 | 0 | 1 | 0 | 2 |
| S9 | 1번 저장해줘 | 저장 + (같은 날 계획이 있으면) 겹침 안내 | status=ok · 저장 #2 · 겹침 1 · Tool: 0회 | 0 | 1 | 0 | 2 |
| S10 | 12월 19일 토요일 저녁 대학로 연극 | 추천 정상, 날씨 '예보 범위 밖', 기상청 호출 0회 | status=ok · 추천 5편 (1위 연모 [대학로] 18:00→19:30, 66,000원, 날씨 out_of_range) · Tool: search_performances×1, get_performance_detail×10, get_weather×1 | 0 | 1 | 12 | 5720 |
| S11 | 토요일 밤 대학로 비 와? | 장소 검색 → 날씨만 조회 | status=ok · facts: 21시 강수확률 0% · 기온 -1℃ · Tool: search_places×1, get_weather×1 | 0 | 1 | 2 | 1179 |

출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr) · 카카오맵 · 기상청 단기예보(공공누리 제1유형)
