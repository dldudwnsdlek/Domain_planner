"""EventBus · 로깅 Agent · SQLite 저장소 (F3012~F3015)."""

import ast
import pathlib

from app.db.database import Database
from app.db.logs_repo import LogsRepo
from app.db.plans_repo import PlansRepo
from app.events.bus import EventBus, RunEmitter
from app.events.types import Event
from app.logging_agent.subscriber import LoggingAgent

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def _imports(package: str) -> set[str]:
    names = set()
    for path in (APP / package).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
    return names


def test_bus_works_without_subscribers():
    RunEmitter(EventBus(), "s", "r").emit("run.started", None, message="hi")


def test_subscriber_exception_is_isolated():
    bus, got = EventBus(), []

    def broken(_event):
        raise RuntimeError("boom")

    bus.subscribe(broken)
    bus.subscribe(got.append)
    RunEmitter(bus, "s", "r").emit("node.entered", "analyze")
    assert len(got) == 1


def test_unsubscribe_stops_delivery():
    bus, got = EventBus(), []
    unsubscribe = bus.subscribe(got.append)
    unsubscribe()
    RunEmitter(bus, "s", "r").emit("node.entered", "analyze")
    assert got == []


def test_seq_increases_per_run():
    em = RunEmitter(EventBus(), "s", "r")
    assert [em.emit("x").seq for _ in range(3)] == [1, 2, 3]


def test_logging_agent_appends_in_order_and_separates_sessions():
    db = Database(":memory:")
    repo = LogsRepo(db)
    bus = EventBus()
    LoggingAgent(repo).attach(bus)
    a, b = RunEmitter(bus, "s-a", "r1"), RunEmitter(bus, "s-b", "r2")
    a.emit("run.started", None, message="A")
    b.emit("run.started", None, message="B")
    a.emit("run.completed", None, elapsed_ms=10)
    assert [e["type"] for e in repo.events("s-a")] == ["run.started", "run.completed"]
    assert [e["payload"]["message"] for e in repo.events("s-b")] == ["B"]
    assert {s["session_id"] for s in repo.list_sessions()} == {"s-a", "s-b"}
    assert repo.delete_session("s-a") == 2 and repo.events("s-a") == []


def test_logging_failure_does_not_raise(capsys):
    class BrokenRepo:
        def append(self, _event):
            raise OSError("disk full")

    LoggingAgent(BrokenRepo()).handle(Event("s", "r", 1, "x", None, {}))
    assert "로그 저장 실패" in capsys.readouterr().err


def test_logs_repo_has_no_update_api():
    assert not [m for m in dir(LogsRepo) if m.startswith(("update", "edit", "modify", "put", "patch"))]


def test_logging_agent_never_imports_llm():
    imported = _imports("logging_agent")
    assert not any(n.startswith(("langchain", "openai", "app.llm", "app.agent")) for n in imported)


def test_agent_does_not_import_logging_agent():
    assert not any(n.startswith("app.logging_agent") for n in _imports("agent"))


def test_plans_saved_even_when_overlapping():
    repo = PlansRepo(Database(":memory:"))
    base = {"performance_id": "P", "title": "A", "date": "2026-11-21"}
    first, overlaps = repo.create({**base, "start_time": "19:00", "end_time": "21:00"})
    assert overlaps == []
    second, overlaps = repo.create({**base, "title": "B", "start_time": "20:00", "end_time": "22:00"})
    assert [o["id"] for o in overlaps] == [first["id"]]
    listed = repo.list()
    assert [p["overlaps"] for p in listed] == [[second["id"]], [first["id"]]]
    updated, overlaps = repo.update(second["id"], {"start_time": "21:00", "title": "무시됨"})
    assert updated["start_time"] == "21:00" and updated["title"] == "B" and overlaps == []
    assert repo.delete(first["id"]) and repo.get(first["id"]) is None
    assert repo.update(999, {"memo": "x"}) is None
