"""예시 화면용 데이터(frontend/demo-data.js)를 저장된 실제 샘플로 만든다. 외부 호출 0회, LLM 0회.

실행: .venv/bin/python scripts/make_demo_data.py

- 요청 분석(LLM 담당)만 S1 조건으로 고정하고, 나머지는 실제 Agent 그래프를 샘플 응답으로 실행한다.
- 결과는 화면 예시이며, 실제 서비스에서는 /api/chat 응답이 같은 형식으로 온다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.offline import run_offline_s1  # noqa: E402

OUT = ROOT / "frontend" / "demo-data.js"


def main() -> int:
    chat, plans, logs = run_offline_s1(now=datetime(2026, 11, 20, 8, 41))
    js = (
        "// 자동 생성: scripts/make_demo_data.py — 저장된 실제 API 샘플 + 실제 판정 엔진, 요청 분석만 고정값\n"
        f"window.DEMO_DATA = {json.dumps({'chat': chat, 'plans': plans, 'logs': logs}, ensure_ascii=False, indent=1)};\n"
        + DEMO_API
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"저장: {OUT.relative_to(ROOT)} · 추천 {len(chat['recommendations'])}편 · 제외 {len(chat['excluded'])}편")
    return 0


DEMO_API = r"""
(function () {
  const D = window.DEMO_DATA;
  let plans = JSON.parse(JSON.stringify(D.plans));
  let nextId = 100;
  const overlap = (a, b) => a.date === b.date && a.start_time < (b.end_time || b.start_time) && (a.end_time || a.start_time) > b.start_time;
  const withOverlaps = () => plans.map((p) => ({ ...p, overlaps: plans.filter((q) => q.id !== p.id && overlap(p, q)).map((q) => q.id) }));
  window.demoApi = async function (method, path, body) {
    await new Promise((r) => setTimeout(r, method === "POST" && path === "/api/chat" ? 700 : 80));
    if (path === "/api/health") return { status: "ok", services: { kopis: true, kakao: true, kma: true, llm: false } };
    if (path === "/api/chat") return D.chat;
    if (path === "/api/plans" && method === "GET") return { plans: withOverlaps() };
    if (path === "/api/plans" && method === "POST") {
      const plan = { ...body, id: nextId++, created_at: new Date().toISOString() };
      const overlaps = plans.filter((q) => overlap(plan, q));
      plans.push(plan);
      return { plan, overlaps };
    }
    const m = path.match(/^\/api\/plans\/(\d+)$/);
    if (m && method === "PATCH") { const p = plans.find((x) => x.id == m[1]); Object.assign(p, body); return { plan: p, overlaps: [] }; }
    if (m && method === "DELETE") { plans = plans.filter((x) => x.id != m[1]); return { deleted: true }; }
    if (path === "/api/logs") return { sessions: D.logs.sessions };
    if (path.startsWith("/api/logs/") && method === "GET") return { events: D.logs.events };
    if (path.startsWith("/api/logs/") && method === "DELETE") return { deleted: D.logs.events.length };
    throw { code: "NOT_FOUND", message: "예시 모드에서 지원하지 않는 요청이에요." };
  };
  window.DEMO_AUTOPLAY = function (renderReply, addMessage) {
    addMessage("user", D.chat.request);
    renderReply(D.chat);
  };
})();
"""

if __name__ == "__main__":
    sys.exit(main())
