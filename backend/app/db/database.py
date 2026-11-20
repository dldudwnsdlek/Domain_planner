"""SQLite 연결과 테이블. 스레드 안전을 위해 연결 하나 + 잠금을 쓴다."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS plans (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  performance_id TEXT NOT NULL,
  title          TEXT NOT NULL,
  venue_name     TEXT,
  venue_address  TEXT,
  date           TEXT NOT NULL,
  start_time     TEXT NOT NULL,
  end_time       TEXT,
  price          INTEGER,
  ticket_url     TEXT,
  memo           TEXT,
  session_id     TEXT,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plans_date ON plans(date);

CREATE TABLE IF NOT EXISTS execution_logs (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id   TEXT NOT NULL UNIQUE,
  session_id TEXT NOT NULL,
  run_id     TEXT NOT NULL,
  seq        INTEGER NOT NULL,
  ts         TEXT NOT NULL,
  type       TEXT NOT NULL,
  node       TEXT,
  payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_session ON execution_logs(session_id, run_id, seq);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]
