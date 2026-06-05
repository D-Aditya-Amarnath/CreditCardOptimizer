from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from agent4_gradio_rag.backend.deps import get_current_user
from shared_core.models import UserProfile
from shared_core.database import DatabaseManager
from services.vector_store import HierarchicalVectorStore
from agent4_gradio_rag.rag_service import RagService
from agent4_gradio_rag.conflict_detector import ConflictDetector
from agent4_gradio_rag.retrieval_planner import RetrievalPlanner
from agent4_gradio_rag.prompt_builder import build_prompt
from agent4_gradio_rag.context_compressor import ContextCompressor
from agent4_gradio_rag.retrieval_auditor import RetrievalAuditor

router = APIRouter(prefix="/chat")
db = DatabaseManager()
vector_store = HierarchicalVectorStore()
conflict_detector = ConflictDetector()
retrieval_planner = RetrievalPlanner()
prompt_builder_type = type('prompt_builder', (), {
    'build_prompt': staticmethod(build_prompt)
})()
context_compressor = ContextCompressor()
auditor = RetrievalAuditor()

rag_service = RagService(
    vector_store=vector_store,
    conflict_detector=conflict_detector,
    retrieval_planner=retrieval_planner,
    prompt_builder=prompt_builder_type,
    context_compressor=context_compressor,
    auditor=auditor,
)


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, user: UserProfile = Depends(get_current_user)):
    user_cards = db.get_user_cards(user.id)
    stats = db.get_dashboard_stats(user.id)
    return {
        "request": request,
        "user": user,
        "user_cards": user_cards,
        "stats": stats,
    }


@router.get("/api/chat/stream")
async def chat_stream(message: str, user: UserProfile = Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    import json

    user_cards = [c.card_name for c in db.get_user_cards(user.id)]

    def event_generator():
        result = rag_service.query(
            user_input=message,
            user_id=user.id,
            user_cards=user_cards,
        )

        if result["type"] == "command":
            yield f"data: {json.dumps({'type': 'command', **result})}\n\n"
            return

        answer = result["answer"]
        for i in range(0, len(answer), 15):
            chunk = answer[i:i+15]
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'meta': {
            'results_count': result.get('results_count', 0),
            'conflicts': len(result.get('conflicts', [])),
            'intent': result.get('intent', 'search'),
        })}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/api/chat/query")
async def chat_query(message: str, user: UserProfile = Depends(get_current_user)):
    user_cards = [c.card_name for c in db.get_user_cards(user.id)]
    result = rag_service.query(
        user_input=message,
        user_id=user.id,
        user_cards=user_cards,
    )
    return result
