"""실행 로그 조회·삭제. 수정(PUT/PATCH) 경로는 일부러 두지 않는다 — 기록을 고칠 수 있으면 관찰의 의미가 없다."""

from fastapi import APIRouter, Depends

from app.api.deps import container
from app.schemas.models import Deleted, EventList, SessionList

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=SessionList, summary="세션별 실행 로그 목록")
def list_sessions(c=Depends(container)):
    return {"sessions": c.logs.list_sessions()}


@router.get("/{session_id}", response_model=EventList, summary="실행 순서대로 이벤트 상세")
def session_events(session_id: str, run_id: str | None = None, c=Depends(container)):
    return {"events": c.logs.events(session_id, run_id)}


@router.delete("/{session_id}", response_model=Deleted, summary="세션 로그 삭제")
def delete_session(session_id: str, c=Depends(container)):
    return {"deleted": c.logs.delete_session(session_id)}
