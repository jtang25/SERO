from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..services import llm_orchestrator

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    view_state: dict | None = None

@router.post("")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    return llm_orchestrator.handle_message(db, req.message, req.view_state or {})
