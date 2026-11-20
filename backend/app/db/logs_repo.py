"""실행 로그 저장소: 추가(append)·조회·세션 삭제만 있다. 수정 메서드는 일부러 두지 않는다."""

from __future__ import annotations

import json

from app.db.database import Database


class LogsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, event: dict) -> None:
        self.db.execute(
            "INSERT INTO execution_logs (event_id, session_id, run_id, seq, ts, type, node, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event["event_id"], event["session_id"], event["run_id"], event["seq"], event["ts"],
             event["type"], event.get("node"), json.dumps(event["payload"], ensure_ascii=False, default=str)))

    def list_sessions(self) -> list[dict]:
        return self.db.query(
            "SELECT session_id, COUNT(DISTINCT run_id) AS runs, COUNT(*) AS events, "
            "MIN(ts) AS first_ts, MAX(ts) AS last_ts FROM execution_logs GROUP BY session_id ORDER BY last_ts DESC")

    def events(self, session_id: str, run_id: str | None = None) -> list[dict]:
        sql = "SELECT event_id, session_id, run_id, seq, ts, type, node, payload FROM execution_logs WHERE session_id = ?"
        params: tuple = (session_id,)
        if run_id:
            sql += " AND run_id = ?"
            params += (run_id,)
        rows = self.db.query(sql + " ORDER BY ts, run_id, seq", params)
        for row in rows:
            row["payload"] = json.loads(row["payload"])
        return rows

    def delete_session(self, session_id: str) -> int:
        return self.db.execute("DELETE FROM execution_logs WHERE session_id = ?", (session_id,)).rowcount
