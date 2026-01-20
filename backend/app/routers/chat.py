from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..db import get_db
from ..services import rag_service

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    view_state: dict | None = None

@router.post("")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    history = [msg.model_dump() for msg in req.history]
    return rag_service.handle_chat(db, req.message, history, req.view_state or {})


@router.post("/stream")
def chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    history = [msg.model_dump() for msg in req.history]
    generator = rag_service.stream_chat(
        db,
        req.message,
        history,
        req.view_state or {},
    )
    return StreamingResponse(generator, media_type="text/event-stream")
