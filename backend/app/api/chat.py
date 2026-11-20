from fastapi import APIRouter, Depends

from app.api.deps import container
from app.schemas.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="대화 요청 (Agent 실행)")
def chat(body: ChatRequest, c=Depends(container)) -> dict:
    # 그래프는 동기 코드라 def 엔드포인트로 두면 FastAPI가 스레드풀에서 실행한다
    return c.service.chat(body.session_id, body.message)
