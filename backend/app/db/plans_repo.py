"""관람 계획 저장소. 겹쳐도 저장하고, 겹치는 계획 목록을 함께 돌려준다."""

from __future__ import annotations

from datetime import datetime

from app.agent.constraints import plans_overlap
from app.db.database import Database
from app.events.types import KST

FIELDS = ("performance_id", "title", "venue_name", "venue_address", "date", "start_time", "end_time",
          "price", "ticket_url", "memo", "session_id")
EDITABLE = ("date", "start_time", "end_time", "memo")


class PlansRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, plan: dict) -> tuple[dict, list[dict]]:
        now = datetime.now(KST).isoformat(timespec="seconds")
        values = [plan.get(f) for f in FIELDS]
        cur = self.db.execute(
            f"INSERT INTO plans ({', '.join(FIELDS)}, created_at, updated_at) "
            f"VALUES ({', '.join('?' * len(FIELDS))}, ?, ?)", (*values, now, now))
        saved = self.get(cur.lastrowid)
        return saved, self.overlaps_for(saved)

    def get(self, plan_id: int) -> dict | None:
        rows = self.db.query("SELECT * FROM plans WHERE id = ?", (plan_id,))
        return rows[0] if rows else None

    def list(self, date: str | None = None) -> list[dict]:
        if date:
            rows = self.db.query("SELECT * FROM plans WHERE date = ? ORDER BY date, start_time", (date,))
        else:
            rows = self.db.query("SELECT * FROM plans ORDER BY date, start_time")
        for row in rows:
            row["overlaps"] = [o["id"] for o in rows if o["id"] != row["id"] and plans_overlap(row, o)]
        return rows

    def update(self, plan_id: int, changes: dict) -> tuple[dict, list[dict]] | None:
        fields = {k: v for k, v in changes.items() if k in EDITABLE}
        if not self.get(plan_id):
            return None
        if fields:
            now = datetime.now(KST).isoformat(timespec="seconds")
            sets = ", ".join(f"{k} = ?" for k in fields)
            self.db.execute(f"UPDATE plans SET {sets}, updated_at = ? WHERE id = ?", (*fields.values(), now, plan_id))
        saved = self.get(plan_id)
        return saved, self.overlaps_for(saved)

    def delete(self, plan_id: int) -> bool:
        return self.db.execute("DELETE FROM plans WHERE id = ?", (plan_id,)).rowcount > 0

    def overlaps_for(self, plan: dict) -> list[dict]:
        same_day = self.db.query("SELECT * FROM plans WHERE date = ? AND id != ?", (plan["date"], plan["id"]))
        return [p for p in same_day if plans_overlap(plan, p)]
