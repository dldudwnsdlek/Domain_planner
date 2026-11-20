"""검증 시나리오를 '실제 외부 API'로 실행한다. LLM이 하는 요청 분석만 고정값으로 넣는다.

실행: .venv/bin/python scripts/run_scenarios_without_llm.py
출력: docs/verification_without_llm.md (기대 동작 / 실제 동작 / 재계획 / LLM·API 호출 수)
- LLM(GMS)을 쓸 수 없을 때 analyze 이후 단계(plan 규칙 템플릿·execute·judge·replan·enrich·respond)를 검증하는 용도.
- 키는 출력·저장하지 않는다. 외부 호출은 캐시를 공유해 최소화한다.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.database import Database  # noqa: E402
from app.offline import FixedAnalyzer, S1, S1_MESSAGE, SAVE_1, analysis, build_offline  # noqa: E402

OUT = ROOT / "docs" / "verification_without_llm.md"
TOMORROW_SAT = "2026-11-21"

SCENARIOS = [
    ("S1", S1_MESSAGE, S1, "통과 ≥ 1, 재계획 0"),
    ("S3", "토요일 밤 10시 이후 시작하는 뮤지컬, 2만원 이하",
     analysis("plan_request", "늦은 시각·저예산", date=TOMORROW_SAT, start_after="22:00", genre="뮤지컬",
              budget_max=20000), "재계획 3회 후 중단 + 탈락 원인 통계 + 조정안"),
    ("S5", "안녕! 이거 어떻게 써?", analysis("chitchat", "인사"), "계획 생략, Tool 0회"),
    ("S6", "같은 날 뮤지컬로 바꿔줘", analysis("plan_request", "장르만 변경", genre="뮤지컬"),
     "날짜·시각·예산 유지, 장르만 변경"),
    ("S7", "'아일랜드' 러닝타임이랑 관람등급 알려줘",
     analysis("fact_query", "사실 조회", topic="performance", keyword="아일랜드"), "검색 → 상세 → 사실 응답 (판정 없음)"),
    ("S8", "토요일에 연극 보고 집에 11시 반까지 가야 해",
     analysis("plan_request", "집 위치 없음", date=TOMORROW_SAT, genre="연극", home_by="23:30"), "Tool 호출 전 되묻기"),
    ("S9", "1번 저장해줘", SAVE_1, "저장 + (같은 날 계획이 있으면) 겹침 안내"),
    ("S10", "12월 19일 토요일 저녁 대학로 연극",
     analysis("plan_request", "예보 범위 밖", date="2026-12-19", start_after="18:00", region="대학로", genre="연극"),
     "추천 정상, 날씨 '예보 범위 밖', 기상청 호출 0회"),
    ("S11", "토요일 밤 대학로 비 와?",
     analysis("fact_query", "날씨만", topic="weather", date=TOMORROW_SAT, region="대학로", start_after="21:00"),
     "장소 검색 → 날씨만 조회"),
]


def describe(resp: dict, events: list[dict]) -> str:
    tools = [e["payload"]["tool"] for e in events if e["type"] == "tool.requested"]
    counts = {t: tools.count(t) for t in dict.fromkeys(tools)}
    parts = [f"status={resp['status']}"]
    if resp["recommendations"]:
        r = resp["recommendations"][0]
        s = r["showtimes"][0]
        parts.append(f"추천 {len(resp['recommendations'])}편 (1위 {r['title']} {s['start']}→{s['end']}"
                     + (f"→도착 {s['home_arrival']}" if s.get("home_arrival") else "") + f", {r['min_price']:,}원, "
                     f"날씨 {r['weather']['status']})")
    if resp.get("facts"):
        f = resp["facts"]
        parts.append("facts: " + (f"{f.get('title')} {f.get('runtime_min')}분 {f.get('age_rating')}" if f.get("title")
                                  else f.get("summary") or f.get("message", "")))
    if resp.get("saved_plan"):
        parts.append(f"저장 #{resp['saved_plan']['id']} · 겹침 {len(resp['overlaps'])}")
    if resp["suggestions"]:
        parts.append("조정안: " + " / ".join(s["text"] for s in resp["suggestions"]))
    if resp["status"] in ("clarify", "limit_reached"):
        parts.append("응답: " + resp["reply"].replace("\n", " "))
    parts.append("Tool: " + (", ".join(f"{t}×{n}" for t, n in counts.items()) or "0회"))
    return " · ".join(parts)


def main() -> int:
    now = datetime.now()
    table = {msg: out for _, msg, out, _ in SCENARIOS}
    service, plans, logs = build_offline(now, FixedAnalyzer(table), Database(":memory:"))
    rows = []
    for sid, msg, _, expected in SCENARIOS:
        session = "s-main" if sid in ("S1", "S6", "S9") else f"s-{sid.lower()}"
        if sid == "S9":  # 같은 날 계획을 하나 먼저 만들어 겹침을 재현
            service.chat(session, S1_MESSAGE)
            service.chat(session, msg)
        resp = service.chat(session, msg)
        events = logs.events(session, resp["run_id"])
        done = next((e for e in events if e["type"] == "run.completed"), {"payload": {}})["payload"]
        rows.append((sid, msg, expected, describe(resp, events), resp["replan_count"],
                     done.get("llm_calls"), done.get("api_calls"), done.get("elapsed_ms")))
        print(f"{sid}: {resp['status']} · 재계획 {resp['replan_count']} · Tool 호출 {done.get('api_calls')}회")

    lines = [
        "# 검증 결과 — LLM 없이 실제 API로 실행 (요청 분석만 고정값)", "",
        f"- 실행 시각: {now.isoformat(timespec='minutes')}",
        "- 실행 방법: `.venv/bin/python scripts/run_scenarios_without_llm.py`",
        "- 범위: analyze(LLM) 결과를 고정값으로 넣고, plan(규칙 템플릿) · execute · judge · replan · enrich · respond를 "
        "실제 KOPIS·카카오·기상청 API로 실행했다. LLM 호출은 0회다(GMS 429로 사용 불가).",
        "- S2·S4는 이 표에 없다: S2는 실제 데이터에서 1차에 통과해 재계획이 재현되지 않을 수 있고, "
        "S4(기상청 키 제거)는 `backend/tests/test_graph.py::test_s4_*`로 검증한다.", "",
        '- **LLM 칸은 실제 LLM 호출이 아니라 분석 대역(고정값) 호출 수다.** 실제 LLM 호출은 0회다.\n- S10의 `get_weather×1`은 Tool이 예보 범위를 먼저 검사해 `OUT_OF_RANGE`로 끝낸 것으로, 기상청 API 호출은 0회다.', "",
        "| ID | 요청 | 기대 동작 | 실제 동작 | 재계획 | LLM(대역) | Tool 호출 | 시간(ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c).replace("|", "/") for c in row) + " |")
    lines += ["", "출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr) · 카카오맵 · 기상청 단기예보(공공누리 제1유형)"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
