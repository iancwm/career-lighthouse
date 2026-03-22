# api/models.py
from pydantic import BaseModel
from typing import Optional

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    resume_text: Optional[str] = None
    history: list[ChatMessage] = []

class Citation(BaseModel):
    filename: str
    excerpt: str

class ChatResponse(BaseModel):
    response: str
    citations: list[Citation]

class BriefRequest(BaseModel):
    resume_text: str

class BriefResponse(BaseModel):
    brief: str

class DocInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    uploaded_at: str

class IngestResponse(BaseModel):
    doc_id: str
    chunk_count: int
    status: str

class DeleteResponse(BaseModel):
    status: str  # "deleted" | "not_found"
