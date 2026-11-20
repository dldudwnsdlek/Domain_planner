from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import container
from app.schemas.models import Deleted, PlanCreate, PlanList, PlanResult, PlanUpdate

router = APIRouter(prefix="/api/plans", tags=["plans"])


def _not_found():
    return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "계획을 찾지 못했어요."})


@router.get("", response_model=PlanList, summary="계획 목록 (겹치는 계획 id 포함)")
def list_plans(date: str | None = None, c=Depends(container)):
    return {"plans": c.plans.list(date)}


@router.get("/{plan_id}", response_model=PlanResult, summary="계획 상세")
def get_plan(plan_id: int, c=Depends(container)):
    plan = c.plans.get(plan_id)
    if not plan:
        raise _not_found()
    return {"plan": plan, "overlaps": c.plans.overlaps_for(plan)}


@router.post("", response_model=PlanResult, status_code=201, summary="계획 저장 (겹쳐도 저장하고 겹침 목록 반환)")
def create_plan(body: PlanCreate, c=Depends(container)):
    plan, overlaps = c.plans.create(body.model_dump())
    return {"plan": plan, "overlaps": overlaps}


@router.patch("/{plan_id}", response_model=PlanResult, summary="날짜·시각·메모 수정")
def update_plan(plan_id: int, body: PlanUpdate, c=Depends(container)):
    result = c.plans.update(plan_id, body.model_dump(exclude_unset=True))
    if not result:
        raise _not_found()
    plan, overlaps = result
    return {"plan": plan, "overlaps": overlaps}


@router.delete("/{plan_id}", response_model=Deleted, summary="계획 삭제")
def delete_plan(plan_id: int, c=Depends(container)):
    if not c.plans.delete(plan_id):
        raise _not_found()
    return {"deleted": True}
