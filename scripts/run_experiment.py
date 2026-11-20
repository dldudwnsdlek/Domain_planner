"""(심화 F3021) 구성 A/B/C 비교 실험 — 실제 LLM(GMS) + 실제 외부 API.

실행: .venv/bin/python scripts/run_experiment.py [--repeats 3]
출력: docs/experiment.md (결과 표·방법·해석), docs/logs/experiment_runs.json (실행별 원자료, 실행마다 저장)

구성
  A  필수 구현(단일 Agent)
  B  Planner·Worker, Worker LLM 끔  — 복구 가능한 실패도 규칙으로 Planner에게 넘김
  C  Planner·Worker, Worker LLM 켬  — 복구 가능한 실패에서만 LLM이 재시도·건너뜀·재계획 요청 선택

시나리오: S1~S9(S2는 재계획이 실제로 일어나는 S2′) + W1~W3(집 위치 표현을 카카오가 못 찾는 경우, 실측 NO_RESULT)
측정 방법
  - 먼저 모든 시나리오를 한 번 실행해 API 응답 캐시를 채운다(측정 제외). KOPIS 응답 지연(건당 1.2~5.4초 관측)이
    구조 차이를 가리지 않게 하기 위해서다. 외부 API 호출 수는 캐시와 무관한 'Tool 호출 수'로 센다.
  - 반복마다 구성 실행 순서를 돌려(A→B→C, B→C→A, C→A→B) 순서 효과를 줄인다.
  - 모든 값은 실행 로그 이벤트(run.completed · llm.decision · tool.requested)에서 자동 집계한다.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.llm_steps import LLMWorker  # noqa: E402
from app.db.database import Database  # noqa: E402
from app.main import build_container  # noqa: E402
from app.tools import base  # noqa: E402
from app.tools.redact import assert_no_secrets, configured_secrets  # noqa: E402

DOCS = ROOT / "docs"
RAW = DOCS / "logs" / "experiment_runs.json"
S1 = "11월 21일 토요일 저녁 6시 이후 대학로에서 연극 보고, 밤 11시 반까지 망원역 도착해야 해. 5만원 이하로."
W_TAIL = "에 가야 해. 5만원 이하"


def tools_of(events):
    return [e["payload"]["tool"] for e in events if e["type"] == "tool.requested"]


def home_outcome(r, e) -> str:
    if r["status"] == "ok" and r["recommendations"] and r["recommendations"][0]["showtimes"][0].get("home_arrival"):
        return "자동 해결"
    if r["status"] == "clarify" and "get_transit_time" not in tools_of(e):
        return "되묻기"
    return "실패"


# (ID, 메시지, 준비, 성공 판정) — 준비: None / "s1"(같은 세션에서 S1 먼저) / "s1+overlap"(+겹치는 계획)
SCENARIOS = [
    ("S1", S1, None, lambda r, e, ctx: r["status"] == "ok" and r["recommendations"] and r["replan_count"] == 0),
    ("S2′", "토요일 대학로 연극, 7시 이후 시작해서 9시 전에 끝나는 걸로, 만원 이하", None,
     lambda r, e, ctx: r["status"] == "ok" and r["recommendations"] and r["replan_count"] >= 1),
    ("S3", "토요일 밤 10시 이후 시작하는 뮤지컬, 2만원 이하", None,
     lambda r, e, ctx: r["status"] == "limit_reached" and r["replan_count"] == 3),
    ("S4", "토요일 6시 이후 대학로 연극, 11시 반까지 망원역 도착", "no_kma",
     lambda r, e, ctx: r["status"] == "ok" and r["recommendations"]
     and all(x["weather"]["status"] == "unavailable" for x in r["recommendations"])),
    ("S5", "안녕! 이거 어떻게 써?", None, lambda r, e, ctx: r["status"] == "ok" and not tools_of(e)),
    ("S6", "같은 날 뮤지컬로 바꿔줘", "s1",
     lambda r, e, ctx: r["understood"].get("genre") == "뮤지컬" and all(
         r["understood"].get(k) == ctx["s1"].get(k) for k in ("date", "start_after", "budget_max", "home_by"))),
    ("S7", "'아일랜드' 러닝타임이랑 관람등급 알려줘", None,
     lambda r, e, ctx: (r.get("facts") or {}).get("runtime_min")
     and tools_of(e) == ["search_performances", "get_performance_detail"]),
    ("S8", "토요일에 연극 보고 집에 11시 반까지 가야 해", None,
     lambda r, e, ctx: r["status"] == "clarify" and not tools_of(e)),
    ("S9", "1번 저장해줘", "s1+overlap", lambda r, e, ctx: r.get("saved_plan") and len(r.get("overlaps") or []) >= 1),
    ("W1", "토요일 저녁 6시 이후 대학로 연극, 밤 11시 반까지 집(망원동 성미산로 근처)" + W_TAIL, None,
     lambda r, e, ctx: home_outcome(r, e) != "실패"),
    ("W2", "토요일 저녁 6시 이후 대학로 연극, 밤 11시 반까지 마포구 망원동 우리 아파트" + W_TAIL, None,
     lambda r, e, ctx: home_outcome(r, e) != "실패"),
    ("W3", "토요일 저녁 6시 이후 대학로 연극, 밤 11시 반까지 합정이랑 망원 사이 우리집" + W_TAIL, None,
     lambda r, e, ctx: home_outcome(r, e) != "실패"),
]


def make_containers(configs):
    out = {}
    for mode in configs:
        out[mode] = build_container(Database(":memory:"), {"mode": mode, "worker": LLMWorker() if mode == "C" else None})
    return out


def run_one(container, mode, sid, message, prep, check, session):
    service, logs = container.service, container.logs
    ctx = {}
    if prep in ("s1", "s1+overlap"):
        setup = service.chat(session, S1)
        ctx["s1"] = setup["understood"]
        if prep == "s1+overlap" and setup["recommendations"]:
            top = setup["recommendations"][0]
            start = datetime.strptime(top["showtimes"][0]["start"], "%H:%M")
            container.plans.create({"performance_id": "MANUAL", "title": "저녁 약속", "date": top["date"],
                                    "start_time": (start - timedelta(minutes=60)).strftime("%H:%M"),
                                    "end_time": (start + timedelta(minutes=30)).strftime("%H:%M")})
    saved_kma = os.environ.get("KMA_SERVICE_KEY", "")
    if prep == "no_kma":
        os.environ["KMA_SERVICE_KEY"] = ""
        base.clear_cache("kma:")
    try:
        r = service.chat(session, message)
    finally:
        if prep == "no_kma":
            os.environ["KMA_SERVICE_KEY"] = saved_kma
    events = logs.events(session, r["run_id"])
    done = next((x["payload"] for x in events if x["type"] == "run.completed"), {})
    worker_llm = sum(1 for x in events if x["type"] == "llm.decision" and x["payload"].get("kind") == "worker_retry")
    rejected = sum(1 for x in events if x["type"] == "worker.rejected")
    record = {"mode": mode, "id": sid, "status": r["status"], "success": bool(check(r, events, ctx)),
              "replan": r["replan_count"], "llm_calls": done.get("llm_calls"), "worker_llm_calls": worker_llm,
              "rejected": rejected, "api_calls": done.get("api_calls"), "elapsed_ms": done.get("elapsed_ms"),
              "outcome": home_outcome(r, events) if sid.startswith("W") else None,
              "notes": r.get("defaults_applied", [])}
    return record


def summarize(rows, configs):
    def avg(xs):
        xs = [x for x in xs if x is not None]
        return statistics.mean(xs) if xs else 0.0

    lines = ["| 구성 | 성공률 | 평균 재계획 | 요청당 LLM 호출 | 그중 Worker LLM | 평균 응답(초) | 외부 API 호출(Tool) |",
             "|---|---|---|---|---|---|---|"]
    for mode in configs:
        rs = [r for r in rows if r["mode"] == mode]
        if not rs:
            continue
        ok = sum(r["success"] for r in rs)
        lines.append(f"| {mode} | {ok}/{len(rs)} ({ok / len(rs):.0%}) | {avg(r['replan'] for r in rs):.2f} | "
                     f"{avg(r['llm_calls'] for r in rs):.2f} | {avg(r['worker_llm_calls'] for r in rs):.2f} | "
                     f"{avg(r['elapsed_ms'] for r in rs) / 1000:.1f} | {avg(r['api_calls'] for r in rs):.1f} |")
    return lines


def write_doc(rows, configs, repeats, started):
    s_rows = [r for r in rows if r["id"].startswith("S")]
    w_rows = [r for r in rows if r["id"].startswith("W")]
    lines = [
        "# 심화 F3021 비교 실험 — 단일 Agent(A) vs Planner·Worker(B: Worker LLM 끔, C: 켬)", "",
        f"- 실행: {started} · `.venv/bin/python scripts/run_experiment.py --repeats {repeats}` · 실제 LLM(GMS claude-haiku-5-5)과 실제 외부 API",
        f"- 시나리오 12개(S1~S9, S2는 재계획이 실제로 일어나는 S2′ + 집 위치 복구 W1~W3) × 구성 3개 × {repeats}회 = {len(rows)}회",
        "- 측정 전 모든 시나리오를 한 번 실행해 API 캐시를 채웠다(KOPIS 지연 변동 제거). 외부 API 호출은 캐시와 무관한 Tool 호출 수",
        "- 성공: 통과 후보 ≥ 1 또는 올바른 되묻기(시나리오별 판정은 `scripts/run_experiment.py`)", "",
        "## 전체", "", *summarize(rows, configs), "",
        "## 정상 경로 (S1~S9)", "", *summarize(s_rows, configs), "",
        "## 복구가 필요한 경로 (W1~W3: 집 위치를 카카오가 못 찾음)", "", *summarize(w_rows, configs), "",
        "| 시나리오 | 구성 | 결과(자동 해결 / 되묻기 / 실패) | 평균 재계획 | 평균 Tool 호출 | Worker가 고친 값(예) |",
        "|---|---|---|---|---|---|",
    ]
    for sid in ("W1", "W2", "W3"):
        for mode in configs:
            rs = [r for r in w_rows if r["id"] == sid and r["mode"] == mode]
            if not rs:
                continue
            counts = {k: sum(1 for r in rs if r["outcome"] == k) for k in ("자동 해결", "되묻기", "실패")}
            note = next((n for r in rs for n in r["notes"] if "고쳐 찾았어요" in n), "")
            lines.append(f"| {sid} | {mode} | {counts['자동 해결']} / {counts['되묻기']} / {counts['실패']} | "
                         f"{statistics.mean(r['replan'] for r in rs):.1f} | "
                         f"{statistics.mean(r['api_calls'] or 0 for r in rs):.1f} | {note} |")
    lines += ["", "## 해석", "", "(실행 결과를 보고 채운다)", ""]
    text = "\n".join(lines) + "\n"
    assert_no_secrets(text, configured_secrets())
    (DOCS / "experiment.md").write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--configs", default="A,B,C")
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()
    configs = args.configs.split(",")
    started = datetime.now().isoformat(timespec="minutes")
    containers = make_containers(configs)
    RAW.parent.mkdir(parents=True, exist_ok=True)

    if not args.no_warmup:
        warm = make_containers(["A"])["A"]
        for sid, msg, prep, check in SCENARIOS:
            try:
                run_one(warm, "A", sid, msg, prep, check, f"warm-{sid}")
                print(f"[warm] {sid}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[warm] {sid} 실패: {type(exc).__name__}", flush=True)

    rows: list[dict] = []
    for rep in range(args.repeats):
        order = configs[rep % len(configs):] + configs[:rep % len(configs)]
        for sid, msg, prep, check in SCENARIOS:
            for mode in order:
                session = f"x-{mode}-{sid}-{rep}"
                try:
                    rec = run_one(containers[mode], mode, sid, msg, prep, check, session)
                except Exception as exc:  # noqa: BLE001 — 실패한 실행도 기록한다
                    rec = {"mode": mode, "id": sid, "status": f"exception:{type(exc).__name__}", "success": False,
                           "replan": None, "llm_calls": None, "worker_llm_calls": 0, "rejected": 0,
                           "api_calls": None, "elapsed_ms": None, "outcome": None, "notes": []}
                rec["repeat"] = rep + 1
                rows.append(rec)
                print(f"[{rep + 1}/{args.repeats}] {sid} {mode}: {'✅' if rec['success'] else '❌'} {rec['status']} "
                      f"재계획 {rec['replan']} LLM {rec['llm_calls']}(Worker {rec['worker_llm_calls']}) "
                      f"Tool {rec['api_calls']} {rec['elapsed_ms']}ms", flush=True)
                text = json.dumps(rows, ensure_ascii=False, indent=1)
                assert_no_secrets(text, configured_secrets())
                RAW.write_text(text + "\n", encoding="utf-8")
                time.sleep(1)  # KOPIS 순간 차단 예방
        write_doc(rows, configs, args.repeats, started)
    print("저장: docs/experiment.md, docs/logs/experiment_runs.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
