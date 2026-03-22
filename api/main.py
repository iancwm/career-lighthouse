# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import docs_router, ingest_router, chat_router, brief_router

app = FastAPI(title="Career Lighthouse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(docs_router.router)
app.include_router(ingest_router.router)
app.include_router(chat_router.router)
app.include_router(brief_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
