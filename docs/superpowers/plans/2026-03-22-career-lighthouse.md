# Career Lighthouse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-sided AI career advisory platform: career office uploads institutional knowledge → students get locally-grounded career advice → counselors get pre-meeting student briefs.

**Architecture:** FastAPI backend (Python) with sentence-transformers embeddings (in-process), Qdrant vector DB (local Docker volume), and Anthropic Claude for generation. Next.js frontend with two routes: `/admin?key=demo2026` (career office) and `/student` (student advisor). The only external API call is Anthropic Claude — all student data stays within the deployment for PDPA compliance.

**Tech Stack:** Python 3.11, FastAPI, sentence-transformers (`all-MiniLM-L6-v2`), qdrant-client, pypdf, python-docx, anthropic SDK, pytest; Next.js 14 (App Router), TypeScript, Tailwind CSS; Docker + docker-compose; Terraform (AWS ap-southeast-1, optional).

**Spec:** `~/.gstack/projects/career-lighthouse/iancwm-master-design-20260322-112228.md`

---

## File Map

```
career-lighthouse/
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml            # pytest pythonpath config
│   ├── main.py                   # FastAPI app, CORS, router mount
│   ├── config.py                 # env vars (ANTHROPIC_API_KEY, ALLOWED_ORIGINS, DATA_PATH)
│   ├── models.py                 # Pydantic request/response schemas
│   ├── dependencies.py           # FastAPI dependency injection (embedder, vector store)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── embedder.py           # sentence-transformers wrapper (singleton)
│   │   ├── vector_store.py       # Qdrant wrapper (init collection, upsert, search, delete)
│   │   ├── ingestion.py          # parse file → chunks → embed → store
│   │   └── llm.py                # Anthropic Claude wrapper (chat + brief)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── docs_router.py        # GET /api/docs, DELETE /api/docs/{doc_id}
│   │   ├── ingest_router.py      # POST /api/ingest
│   │   ├── chat_router.py        # POST /api/chat
│   │   └── brief_router.py       # POST /api/brief
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py           # shared fixtures (in-memory Qdrant, mock embedder)
│       ├── test_embedder.py
│       ├── test_vector_store.py
│       ├── test_ingestion.py
│       ├── test_docs_router.py
│       ├── test_ingest_router.py
│       ├── test_chat_router.py
│       └── test_brief_router.py
├── web/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── middleware.ts              # /admin key guard
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   ├── admin/page.tsx        # career office dashboard
│   │   └── student/page.tsx      # student advisor
│   └── components/
│       ├── admin/
│       │   ├── KnowledgeUpload.tsx
│       │   ├── DocList.tsx
│       │   └── BriefGenerator.tsx
│       └── student/
│           ├── ResumeUpload.tsx
│           ├── ChatInterface.tsx
│           └── CitationBadge.tsx
├── demo-data/
│   ├── nus-alumni-paths.txt
│   ├── gic-recruiting-guide.txt
│   ├── goldman-singapore-guide.txt
│   ├── consulting-paths.txt
│   └── career-office-faq.txt
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Task 1: Repo Scaffold + Demo Data

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `demo-data/nus-alumni-paths.txt`
- Create: `demo-data/gic-recruiting-guide.txt`
- Create: `demo-data/goldman-singapore-guide.txt`
- Create: `demo-data/consulting-paths.txt`
- Create: `demo-data/career-office-faq.txt`

- [ ] **Step 1: Init git and create root files**

```bash
cd /home/iancwm/git/career-lighthouse
git init  # already done
cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
.pytest_cache/
node_modules/
.next/
*.egg-info/
.venv/
venv/
/data/
EOF

cat > .env.example << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
ALLOWED_ORIGINS=http://localhost:3000
DATA_PATH=/data/qdrant
EOF
```

- [ ] **Step 2: Write demo data — NUS alumni paths**

```bash
cat > demo-data/nus-alumni-paths.txt << 'EOF'
NUS Career Paths: Alumni Success Stories

INVESTMENT BANKING
NUS Business School (Finance) → Goldman Sachs Singapore (IBD Analyst)
Typical path: Strong GPA (3.8+), CFA Level 1 before graduation, IBSA club leadership.
NUS typically places 8-12 students annually into BB IBD Singapore. Key firms: GS, MS, JP Morgan, Citi, UBS.
Timeline: Apply in Year 2/3 summer for internships. Full-time offers come from internship conversion (80% rate at GS Singapore 2024).

PUBLIC SECTOR / STATUTORY BOARDS
NUS any faculty → GIC / Temasek / MAS
GIC recruits heavily from NUS across all faculties. Technology roles from SoC, investment roles from Business/Economics.
PSC Scholarship holders from NUS have strong placement into MAS (Monetary Authority of Singapore).
GIC 2024: 40% of Singapore graduate hires from NUS. Interview process: 3 rounds, case study + fit.

CONSULTING
NUS → McKinsey / BCG / Bain Singapore
MBB in Singapore recruit ~15 NUS students per year combined. Target: Business, Engineering, Computing.
McKinsey Singapore holds annual "Problem Solving Workshop" exclusively for NUS students each October.
Bain Singapore has a dedicated NUS campus recruiting team. Apply by September for July start.

TECHNOLOGY
NUS SoC → Google / Meta / Bytedance Singapore
Google Singapore: 20+ NUS SoC hires annually. Focus on SWE and data roles.
Leetcode proficiency (Medium) required. NUS ACM team members have high conversion.
Bytedance Singapore growing fast; less competitive than Google but strong comp packages.
EOF
```

- [ ] **Step 3: Write demo data — GIC recruiting guide**

```bash
cat > demo-data/gic-recruiting-guide.txt << 'EOF'
GIC Private Limited — NUS Recruiting Guide (Career Office Internal)

OVERVIEW
GIC manages Singapore's foreign reserves. ~$700B AUM. Highly prestigious employer.
Actively recruits from NUS. Investment, Technology, Risk, and Operations tracks.

INVESTMENT TRACK
Target: NUS Business (Finance), Economics, Applied Mathematics
Requirements: Strong quantitative ability. GPA 3.7+ preferred. CFA progression valued.
Interview: 3 rounds. Round 1: numerical reasoning + fit. Round 2: investment case study.
Round 3: MD panel. Case: typically a sector analysis or portfolio construction problem.
Timeline: Applications open August. Offers by November for July start.

TECHNOLOGY TRACK
Target: NUS SoC, CEng, Data Science
Requirements: Strong coding (Python/Java), system design awareness.
Interview: Technical coding round + system design + fit.
NUS SoC Career Fair booth every September. GIC CTO attends NUS Tech Talk annually.

TIPS FROM NUS ALUMNI AT GIC
"The case study isn't about getting the right answer — it's about showing structured thinking."
"They value people who ask good questions more than people who have all the answers."
"GIC culture is low-ego, long-term oriented. Don't oversell short-term trading experience."
"Networking at NUS-GIC events matters. They track who shows up."

CONTACTS (Career Office Use Only)
Campus Recruiting Lead: Refer students to careers.gic.com.sg/campus
NUS Alumni at GIC willing to do informational calls: Contact career office for referral list.
EOF
```

- [ ] **Step 4: Write remaining demo data files**

```bash
cat > demo-data/goldman-singapore-guide.txt << 'EOF'
Goldman Sachs Singapore — NUS Campus Recruiting (2024-2025)

DIVISIONS HIRING FROM NUS
Investment Banking Division (IBD): 6-8 analysts/year from NUS
Securities (Equities/FICC): 4-6 analysts/year
Engineering (Technology): 10-15 engineers/year
Asset Management: 2-3 analysts/year

IBD APPLICATION PROCESS
Step 1: Online application (September deadline for summer analyst)
Step 2: HireVue video interview (behavioral + motivational)
Step 3: Superday — 4-6 back-to-back interviews, mix of technical and behavioral
Technical: DCF, LBO concepts, M&A mechanics, current deal awareness
Behavioral: Why GS? Why IBD? Describe a time you worked in a team under pressure.

WHAT GS SINGAPORE LOOKS FOR (from NUS alumni interviews)
- Deal awareness: read the GS press releases, know recent SEA deals
- Quantitative: comfortable with Excel modeling, accounting basics
- Communication: can explain complex concepts simply
- Cultural fit: Goldman culture is intense; show you thrive under pressure

NUS-SPECIFIC ADVANTAGES
GS has a dedicated NUS relationship. Campus Ambassador program (apply separately).
GS Singapore MD is NUS Business alumnus — strong institutional affinity.
NUS IBSA partnership: GS sponsors annual case competition, winners get fast-tracked.
EOF

cat > demo-data/consulting-paths.txt << 'EOF'
Management Consulting from NUS — Career Office Guide

MBB IN SINGAPORE
McKinsey Singapore: 5-7 NUS hires/year. Recruits from all faculties but favors Business/Engineering.
BCG Singapore: 4-6 NUS hires/year. Strong preference for quantitative backgrounds.
Bain Singapore: 4-5 NUS hires/year. Known for culture fit emphasis over pure academics.

APPLICATION TIMELINE
Year 2/3: Apply for summer internships (applications open January, deadline March)
Year 3/4: Apply for full-time analyst roles (applications open August, deadline October)
Internship → full-time conversion rate at MBB Singapore: ~70%

CASE INTERVIEW PREPARATION
NUS Consulting Club runs weekly case practice sessions (every Tuesday, 7pm).
Recommended resources: Case in Point (Cosentino), Victor Cheng videos, NUS case bank.
Partner with 2-3 serious case partners for 50+ case practices before recruiting season.

WHAT SETS NUS CANDIDATES APART
"The NUS candidates who get MBB offers are the ones who can quantify their impact."
"Show regional knowledge — SEA market sizing, ASEAN business dynamics."
"McKinsey Singapore does a lot of government/GLCs work; public policy awareness helps."
EOF

cat > demo-data/career-office-faq.txt << 'EOF'
NUS Career Services — Frequently Asked Questions

Q: I want to go into investment banking. What should I do in Year 1?
A: Join NUS IBSA (Investment Banking Student Association) immediately. Take FIN3101 (Corporate Finance) early. Start reading Financial Times and Bloomberg daily. Get comfortable with Excel. Reach out to NUS alumni in IBD via LinkedIn — most are willing to do 20-minute calls if you're specific about what you want to learn.

Q: Is GPA the most important factor for finance roles?
A: For GS/MS/GIC, 3.7+ is a soft filter for initial screening. However, a 3.6 with strong internships and leadership beats a 3.9 with nothing else. Internship experience (especially relevant internships) matters more than GPA after Year 2.

Q: What's the difference between applying to GIC vs. Temasek?
A: GIC focuses on public markets and manages foreign reserves — more structured recruiting with clear campus timeline. Temasek is more opportunistic in hiring, smaller class sizes, focuses on private markets and portfolio company management. Temasek typically hires more experienced candidates; GIC hires more fresh graduates.

Q: I'm from SoC — can I still go into finance?
A: Absolutely. GIC's technology track is one of the best entry points into the investment industry for engineers. Goldman's technology division is also a strong path. Some SoC students successfully pivot to IBD by doing finance internships early and demonstrating business acumen alongside technical skills.

Q: When should I come see a career counselor?
A: Ideally Year 2 before you apply for your first internship. Come with a specific question, not "I don't know what I want to do." The more prepared you are, the more valuable our time together. Use this AI advisor for general questions first — our counselors are best used for personalized strategy and relationship introductions.
EOF
```

- [ ] **Step 5: Write README**

```bash
cat > README.md << 'EOF'
# Career Lighthouse

AI-powered career advisory platform for universities. Career offices upload institutional knowledge; students get locally-grounded career advice; counselors get pre-meeting student briefs.

## Quick Start (Demo)

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
docker compose up
```

- Career office: http://localhost:3000/admin?key=demo2026
- Student advisor: http://localhost:3000/student

## Architecture

- **Backend**: FastAPI (Python) — embeddings via sentence-transformers (in-process), vector DB via Qdrant (local volume), LLM via Anthropic Claude
- **Frontend**: Next.js 14
- **Data stays local**: only Anthropic Claude API call leaves the deployment (PDPA-compliant)

## Production Deployment (AWS ap-southeast-1)

See `terraform/` — deploy to your institution's own AWS account.
EOF
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: repo scaffold, demo data, README"
```

---

## Task 2: Docker + Compose

**Files:**
- Create: `api/Dockerfile`
- Create: `api/requirements.txt`
- Create: `web/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Write api/requirements.txt**

```bash
mkdir -p api
cat > api/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.6
anthropic==0.34.0
sentence-transformers==3.1.1
qdrant-client==1.11.1
pypdf==4.3.1
python-docx==1.1.2
python-multipart==0.0.9
pydantic-settings==2.5.2
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
EOF
```

- [ ] **Step 2: Write api/Dockerfile**

```dockerfile
# api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# sentence-transformers downloads model on first run; cache it in image
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model into the image so first boot is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Scaffold web/package.json and Dockerfile**

```bash
mkdir -p web
cat > web/package.json << 'EOF'
{
  "name": "career-lighthouse-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest"
  },
  "dependencies": {
    "next": "14.2.15",
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "tailwindcss": "^3",
    "autoprefixer": "^10",
    "postcss": "^8",
    "vitest": "^2",
    "@vitejs/plugin-react": "^4",
    "@testing-library/react": "^16",
    "@testing-library/user-event": "^14"
  }
}
EOF

cat > web/Dockerfile << 'EOF'
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
# Accept the API URL as a build arg so it gets baked into the Next.js bundle
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
EOF
```

- [ ] **Step 4: Write docker-compose.yml**

```yaml
# docker-compose.yml
services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    volumes:
      - qdrant_data:/data/qdrant
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-http://localhost:3000}
      - DATA_PATH=/data/qdrant
    restart: unless-stopped

  web:
    build:
      context: ./web
      args:
        # NEXT_PUBLIC_* vars are baked into the Next.js build at image build time.
        # For local demo: http://localhost:8000 (browser calls this from the host machine).
        # For AWS/Terraform: rebuild the image with the actual ALB URL, or use runtime
        # config injection (e.g. next.config.js rewrites) — see Terraform task.
        - NEXT_PUBLIC_API_URL=http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  qdrant_data:
```

- [ ] **Step 5: Commit**

```bash
git add api/Dockerfile api/requirements.txt web/Dockerfile web/package.json docker-compose.yml
git commit -m "chore: Docker and compose setup"
```

---

## Task 3: API — Config + Models + App Skeleton

**Files:**
- Create: `api/config.py`
- Create: `api/models.py`
- Create: `api/main.py`
- Create: `api/tests/conftest.py`

- [ ] **Step 1: Write api/config.py**

```python
# api/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    allowed_origins: str = "http://localhost:3000"
    data_path: str = "/data/qdrant"

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 2: Write api/models.py**

```python
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
```

- [ ] **Step 3: Write api/main.py skeleton**

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

app = FastAPI(title="Career Lighthouse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Write tests/conftest.py**

```python
# api/tests/conftest.py
import pytest
from unittest.mock import MagicMock
import numpy as np

@pytest.fixture
def mock_embedder(monkeypatch):
    """Returns a fixed 384-dim vector for any input."""
    mock = MagicMock()
    mock.encode.return_value = np.ones(384, dtype=np.float32)
    return mock

@pytest.fixture
def in_memory_qdrant():
    """Qdrant client using in-memory storage for tests."""
    from qdrant_client import QdrantClient
    client = QdrantClient(":memory:")
    return client
```

- [ ] **Step 5: Create package `__init__.py` files and pyproject.toml**

```bash
mkdir -p api/services api/routers api/tests
touch api/services/__init__.py api/routers/__init__.py api/tests/__init__.py

cat > api/pyproject.toml << 'EOF'
[tool.pytest.ini_options]
pythonpath = ["."]
asyncio_mode = "auto"
EOF
```

- [ ] **Step 6: Verify app starts**

```bash
cd api
python -m pytest tests/ -v  # should collect 0 tests, no errors
python -c "from main import app; print('OK')"
```

- [ ] **Step 7: Commit**

```bash
git add api/config.py api/models.py api/main.py api/tests/conftest.py \
        api/services/__init__.py api/routers/__init__.py api/tests/__init__.py \
        api/pyproject.toml
git commit -m "feat: API skeleton — config, models, app, package structure"
```

---

## Task 4: API — Embedder Service

**Files:**
- Create: `api/services/embedder.py`
- Create: `api/tests/test_embedder.py`

- [ ] **Step 1: Write failing test**

```python
# api/tests/test_embedder.py
import numpy as np
from services.embedder import Embedder

def test_embed_returns_correct_dimension():
    embedder = Embedder()
    vec = embedder.encode("hello world")
    assert vec.shape == (384,)
    assert vec.dtype == np.float32

def test_embed_batch_returns_correct_shape():
    embedder = Embedder()
    vecs = embedder.encode_batch(["hello", "world"])
    assert vecs.shape == (2, 384)

def test_embed_same_text_same_vector():
    embedder = Embedder()
    v1 = embedder.encode("career advice")
    v2 = embedder.encode("career advice")
    np.testing.assert_array_equal(v1, v2)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd api && python -m pytest tests/test_embedder.py -v
# Expected: ModuleNotFoundError or ImportError
```

- [ ] **Step 3: Write api/services/embedder.py**

```python
# api/services/embedder.py
import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"

class Embedder:
    _instance = None

    def __new__(cls):
        # Singleton — model loads once per process
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = SentenceTransformer(_MODEL_NAME)
        return cls._instance

    def encode(self, text: str) -> np.ndarray:
        return self._model.encode(text, normalize_embeddings=True).astype(np.float32)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd api && python -m pytest tests/test_embedder.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add api/services/embedder.py api/tests/test_embedder.py
git commit -m "feat: embedder service (sentence-transformers all-MiniLM-L6-v2)"
```

---

## Task 5: API — Vector Store Service

**Files:**
- Create: `api/services/vector_store.py`
- Create: `api/tests/test_vector_store.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_vector_store.py
import numpy as np
import pytest
from services.vector_store import VectorStore

COLLECTION = "knowledge"

@pytest.fixture
def store(in_memory_qdrant):
    vs = VectorStore(client=in_memory_qdrant, collection=COLLECTION)
    vs.ensure_collection(dim=384)
    return vs

def test_upsert_and_search(store):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "test-1",
        "vector": vec,
        "payload": {"source_filename": "test.txt", "chunk_index": 0,
                    "upload_timestamp": "2026-01-01T00:00:00", "text": "career advice"}
    }])
    results = store.search(vec, top_k=1)
    assert len(results) == 1
    assert results[0]["payload"]["source_filename"] == "test.txt"
    assert results[0]["payload"]["text"] == "career advice"

def test_delete_by_filename(store):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "del-1",
        "vector": vec,
        "payload": {"source_filename": "remove.txt", "chunk_index": 0,
                    "upload_timestamp": "2026-01-01T00:00:00", "text": "to delete"}
    }])
    store.delete_by_filename("remove.txt")
    results = store.search(vec, top_k=10)
    filenames = [r["payload"]["source_filename"] for r in results]
    assert "remove.txt" not in filenames

def test_list_docs(store):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([
        {"id": "a-0", "vector": vec, "payload": {"source_filename": "a.txt", "chunk_index": 0,
          "upload_timestamp": "2026-01-01T00:00:00", "text": "chunk a"}},
        {"id": "a-1", "vector": vec, "payload": {"source_filename": "a.txt", "chunk_index": 1,
          "upload_timestamp": "2026-01-01T00:00:00", "text": "chunk a2"}},
        {"id": "b-0", "vector": vec, "payload": {"source_filename": "b.txt", "chunk_index": 0,
          "upload_timestamp": "2026-01-02T00:00:00", "text": "chunk b"}},
    ])
    docs = store.list_docs()
    assert len(docs) == 2
    doc_a = next(d for d in docs if d["filename"] == "a.txt")
    assert doc_a["chunk_count"] == 2
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd api && python -m pytest tests/test_vector_store.py -v
```

- [ ] **Step 3: Write api/services/vector_store.py**

```python
# api/services/vector_store.py
import numpy as np
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)

class VectorStore:
    def __init__(self, client: QdrantClient, collection: str = "knowledge"):
        self._client = client
        self._collection = collection

    def ensure_collection(self, dim: int = 384):
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, points: list[dict]):
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(id=p["id"], vector=p["vector"].tolist(), payload=p["payload"])
                for p in points
            ],
        )

    def search(self, vector: np.ndarray, top_k: int = 5) -> list[dict]:
        results = self._client.search(
            collection_name=self._collection,
            query_vector=vector.tolist(),
            limit=top_k,
            with_payload=True,
        )
        return [{"score": r.score, "payload": r.payload} for r in results]

    def delete_by_filename(self, filename: str):
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="source_filename", match=MatchValue(value=filename))]
            ),
        )

    def list_docs(self) -> list[dict]:
        """Returns [{doc_id, filename, chunk_count, uploaded_at}] aggregated by filename."""
        all_points, _ = self._client.scroll(
            collection_name=self._collection,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        docs: dict[str, dict] = {}
        for pt in all_points:
            fname = pt.payload["source_filename"]
            ts = pt.payload.get("upload_timestamp", "")
            if fname not in docs:
                docs[fname] = {"doc_id": fname, "filename": fname, "chunk_count": 0, "uploaded_at": ts}
            docs[fname]["chunk_count"] += 1
        return list(docs.values())
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd api && python -m pytest tests/test_vector_store.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add api/services/vector_store.py api/tests/test_vector_store.py
git commit -m "feat: vector store service (Qdrant local)"
```

---

## Task 6: API — Ingestion Service

**Files:**
- Create: `api/services/ingestion.py`
- Create: `api/tests/test_ingestion.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/test_ingestion.py
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from services.ingestion import chunk_text, parse_file, ingest_document

def test_chunk_text_splits_on_token_boundary():
    text = " ".join([f"word{i}" for i in range(200)])
    chunks = chunk_text(text, max_tokens=50, overlap=10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 60  # allow slight overage for overlap

def test_chunk_text_single_chunk_if_short():
    text = "short text here"
    chunks = chunk_text(text, max_tokens=512, overlap=64)
    assert chunks == ["short text here"]

def test_parse_file_txt():
    content = b"hello career world"
    text = parse_file(content, "test.txt")
    assert "hello career world" in text

def test_ingest_document_calls_upsert(in_memory_qdrant, mock_embedder):
    from services.vector_store import VectorStore
    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(dim=384)

    mock_embedder.encode_batch.return_value = np.ones((2, 384), dtype=np.float32)

    count = ingest_document(
        file_content=b"chunk one content. " * 60 + b"chunk two content. " * 60,
        filename="test.txt",
        embedder=mock_embedder,
        store=store,
    )
    assert count >= 1
    mock_embedder.encode_batch.assert_called_once()
    docs = store.list_docs()
    assert any(d["filename"] == "test.txt" for d in docs)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd api && python -m pytest tests/test_ingestion.py -v
```

- [ ] **Step 3: Write api/services/ingestion.py**

```python
# api/services/ingestion.py
import uuid
from datetime import datetime, timezone
import numpy as np

def parse_file(content: bytes, filename: str) -> str:
    """Extract text from PDF, DOCX, or plain text."""
    if filename.lower().endswith(".pdf"):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif filename.lower().endswith(".docx"):
        import io
        from docx import Document
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        return content.decode("utf-8", errors="replace")

def chunk_text(text: str, max_tokens: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping word-based chunks (approx 1 word ≈ 1.3 tokens)."""
    words = text.split()
    word_limit = int(max_tokens / 1.3)
    overlap_words = int(overlap / 1.3)
    if len(words) <= word_limit:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + word_limit, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += word_limit - overlap_words
    return chunks

def ingest_document(file_content: bytes, filename: str, embedder, store) -> int:
    """Parse, chunk, embed, and store a document. Returns chunk count."""
    text = parse_file(file_content, filename)
    chunks = chunk_text(text)
    if not chunks:
        return 0

    vectors = embedder.encode_batch(chunks)
    timestamp = datetime.now(timezone.utc).isoformat()

    points = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{filename}-{i}")),
            "vector": vectors[i],
            "payload": {
                "source_filename": filename,
                "chunk_index": i,
                "upload_timestamp": timestamp,
                "text": chunk,
            },
        }
        for i, chunk in enumerate(chunks)
    ]
    store.upsert(points)
    return len(chunks)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd api && python -m pytest tests/test_ingestion.py -v
# Expected: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add api/services/ingestion.py api/tests/test_ingestion.py
git commit -m "feat: ingestion service (parse, chunk, embed, store)"
```

---

## Task 7: API — LLM Service

**Files:**
- Create: `api/services/llm.py`

No unit tests for the LLM service — it wraps a third-party API. Integration is tested via the router tests with mocks.

- [ ] **Step 1: Write api/services/llm.py**

```python
# api/services/llm.py
import anthropic
from config import settings

_client = None

def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client

SCHOOL_NAME = "NUS (National University of Singapore)"

def chat_with_context(message: str, resume_text: str | None,
                       chunks: list[dict], history: list[dict]) -> str:
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[-10:]
    ) if history else "None"

    user_content = (
        f"Student resume:\n{resume_text or 'Not provided'}\n\n"
        f"School knowledge base:\n{kb_text or 'No documents uploaded yet.'}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Student question: {message}"
    )

    response = get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            f"You are a knowledgeable career advisor at {SCHOOL_NAME}. "
            "Answer questions using the provided school knowledge base. "
            "Always cite which document your advice comes from by name. "
            "Be specific to this school's career paths and recruiting relationships. "
            "If the knowledge base has no relevant information, say so honestly."
        ),
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text

def generate_brief(resume_text: str, chunks: list[dict]) -> str:
    kb_text = "\n\n---\n\n".join(
        f"[{c['payload']['source_filename']}]\n{c['payload']['text']}"
        for c in chunks
    )
    response = get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You are a career counselor assistant. Given a student's resume and "
            "school-specific career knowledge, produce a pre-meeting brief with: "
            "(1) Student's apparent career goals, "
            "(2) Resume gaps vs. target paths, "
            "(3) 3-5 recommended talking points grounded in the knowledge base. "
            "Be concise and actionable."
        ),
        messages=[{"role": "user", "content":
            f"Resume:\n{resume_text}\n\nKnowledge base:\n{kb_text}"}],
    )
    return response.content[0].text
```

- [ ] **Step 2: Commit**

```bash
git add api/services/llm.py
git commit -m "feat: LLM service (Anthropic Claude wrapper)"
```

---

## Task 8: API — Shared Dependencies + Routers

**Files:**
- Create: `api/dependencies.py`
- Create: `api/routers/docs_router.py`
- Create: `api/routers/ingest_router.py`
- Create: `api/routers/chat_router.py`
- Create: `api/routers/brief_router.py`
- Create: `api/tests/test_docs_router.py`
- Create: `api/tests/test_ingest_router.py`
- Create: `api/tests/test_chat_router.py`
- Create: `api/tests/test_brief_router.py`
- Modify: `api/main.py`

- [ ] **Step 1: Write api/dependencies.py**

```python
# api/dependencies.py
from functools import lru_cache
from qdrant_client import QdrantClient
from services.embedder import Embedder
from services.vector_store import VectorStore
from config import settings

@lru_cache
def get_qdrant_client() -> QdrantClient:
    client = QdrantClient(path=settings.data_path)
    return client

@lru_cache
def get_embedder() -> Embedder:
    return Embedder()

@lru_cache
def get_vector_store() -> VectorStore:
    client = get_qdrant_client()
    store = VectorStore(client=client, collection="knowledge")
    store.ensure_collection(dim=384)
    return store
```

- [ ] **Step 2: Write router tests (TDD — write these BEFORE the router implementations)**

```python
# api/tests/test_docs_router.py
import pytest
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

def make_client(in_memory_qdrant):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    return TestClient(app), store

def test_list_docs_empty(in_memory_qdrant):
    client, _ = make_client(in_memory_qdrant)
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert r.json() == []

def test_delete_doc_not_found(in_memory_qdrant):
    client, _ = make_client(in_memory_qdrant)
    r = client.delete("/api/docs/nonexistent.txt")
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
```

```python
# api/tests/test_ingest_router.py
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

def test_ingest_txt_file(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    mock_embedder.encode_batch.return_value = np.ones((1, 384), dtype=np.float32)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    client = TestClient(app)
    r = client.post("/api/ingest", files={"file": ("test.txt", b"hello world career", "text/plain")})
    assert r.status_code == 200
    data = r.json()
    assert data["doc_id"] == "test.txt"
    assert data["chunk_count"] >= 1
    assert data["status"] == "ok"
```

```python
# api/tests/test_chat_router.py
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

def test_chat_returns_response_and_citations(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies, services.llm as llm_module

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{"id": "c1", "vector": vec,
                   "payload": {"source_filename": "guide.txt", "chunk_index": 0,
                               "upload_timestamp": "2026-01-01", "text": "GIC recruits from NUS"}}])
    mock_embedder.encode.return_value = vec
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    with patch.object(llm_module, "chat_with_context", return_value="Here is career advice"):
        client = TestClient(app)
        r = client.post("/api/chat", json={"message": "how do I get into GIC?", "resume_text": None, "history": []})

    assert r.status_code == 200
    data = r.json()
    assert data["response"] == "Here is career advice"
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["filename"] == "guide.txt"
```

```python
# api/tests/test_brief_router.py
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch

def test_brief_returns_brief_text(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies, services.llm as llm_module

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    mock_embedder.encode.return_value = vec
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    with patch.object(llm_module, "generate_brief", return_value="# Student Brief\nGoals: finance"):
        client = TestClient(app)
        r = client.post("/api/brief", json={"resume_text": "NUS Business Year 3, interested in GIC"})

    assert r.status_code == 200
    assert "brief" in r.json()
```

- [ ] **Step 3: Run router tests — expect FAIL (routers not implemented yet)**

```bash
cd api && python -m pytest tests/test_docs_router.py tests/test_ingest_router.py \
  tests/test_chat_router.py tests/test_brief_router.py -v
# Expected: ImportError — routers don't exist yet
```

- [ ] **Step 4: Write router implementations**

```python
# api/routers/docs_router.py
from fastapi import APIRouter, Depends
from models import DocInfo, DeleteResponse
from services.vector_store import VectorStore
from dependencies import get_vector_store

router = APIRouter(prefix="/api")

@router.get("/docs", response_model=list[DocInfo])
def list_docs(store: VectorStore = Depends(get_vector_store)):
    return [DocInfo(**d) for d in store.list_docs()]

@router.delete("/docs/{doc_id}", response_model=DeleteResponse)
def delete_doc(doc_id: str, store: VectorStore = Depends(get_vector_store)):
    docs = store.list_docs()
    if not any(d["filename"] == doc_id for d in docs):
        return DeleteResponse(status="not_found")
    store.delete_by_filename(doc_id)
    return DeleteResponse(status="deleted")
```

```python
# api/routers/ingest_router.py
from fastapi import APIRouter, UploadFile, File, Depends
from models import IngestResponse
from services.ingestion import ingest_document
from services.embedder import Embedder
from services.vector_store import VectorStore
from dependencies import get_embedder, get_vector_store

router = APIRouter(prefix="/api")

@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    content = await file.read()
    filename = file.filename or "upload.txt"
    # Delete existing chunks for this filename before re-ingesting
    store.delete_by_filename(filename)
    chunk_count = ingest_document(content, filename, embedder, store)
    return IngestResponse(doc_id=filename, chunk_count=chunk_count, status="ok")
```

```python
# api/routers/chat_router.py
from fastapi import APIRouter, Depends
from models import ChatRequest, ChatResponse, Citation
from services.embedder import Embedder
from services.vector_store import VectorStore
from services import llm
from dependencies import get_embedder, get_vector_store

router = APIRouter(prefix="/api")

@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    query_vec = embedder.encode(req.message)
    chunks = store.search(query_vec, top_k=5)
    citations = [
        Citation(filename=c["payload"]["source_filename"],
                 excerpt=c["payload"]["text"][:150])
        for c in chunks
    ]
    response_text = llm.chat_with_context(
        message=req.message,
        resume_text=req.resume_text,
        chunks=chunks,
        history=[m.model_dump() for m in req.history],
    )
    return ChatResponse(response=response_text, citations=citations)
```

```python
# api/routers/brief_router.py
from fastapi import APIRouter, Depends
from models import BriefRequest, BriefResponse
from services.embedder import Embedder
from services.vector_store import VectorStore
from services import llm
from dependencies import get_embedder, get_vector_store

router = APIRouter(prefix="/api")

@router.post("/brief", response_model=BriefResponse)
def brief(
    req: BriefRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    query_vec = embedder.encode(req.resume_text[:500])  # embed first 500 chars
    chunks = store.search(query_vec, top_k=10)
    brief_text = llm.generate_brief(resume_text=req.resume_text, chunks=chunks)
    return BriefResponse(brief=brief_text)
```

- [ ] **Step 5: Mount routers in main.py**

```python
# api/main.py  (replace full file)
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
```

- [ ] **Step 6: Run all router tests — expect PASS**

```bash
cd api && python -m pytest tests/ -v
# Expected: all tests pass
```

- [ ] **Step 7: Commit**

```bash
git add api/routers/ api/dependencies.py api/main.py api/tests/test_docs_router.py \
        api/tests/test_ingest_router.py api/tests/test_chat_router.py api/tests/test_brief_router.py
git commit -m "feat: all API routers (ingest, chat, brief, docs)"
```

---

## Task 9: Web — Next.js Scaffold + Middleware

**Files:**
- Create: `web/next.config.js`
- Create: `web/tsconfig.json`
- Create: `web/tailwind.config.ts`
- Create: `web/postcss.config.js`
- Create: `web/middleware.ts`
- Create: `web/app/layout.tsx`
- Create: `web/.env.local.example`

- [ ] **Step 1: Scaffold Next.js config files**

```bash
cd web && npm install

cat > next.config.js << 'EOF'
/** @type {import('next').NextConfig} */
module.exports = { output: "standalone" }
EOF

cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "es2017", "lib": ["dom","dom.iterable","esnext"],
    "allowJs": true, "skipLibCheck": true, "strict": true,
    "noEmit": true, "esModuleInterop": true, "module": "esnext",
    "moduleResolution": "bundler", "resolveJsonModule": true,
    "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{"name": "next"}],
    "paths": {"@/*": ["./*"]}
  },
  "include": ["next-env.d.ts","**/*.ts","**/*.tsx",".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
EOF

cat > tailwind.config.ts << 'EOF'
import type { Config } from "tailwindcss"
export default { content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"], theme: { extend: {} }, plugins: [] } satisfies Config
EOF

cat > postcss.config.js << 'EOF'
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }
EOF

cat > .env.local.example << 'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
cp .env.local.example .env.local
```

- [ ] **Step 2: Write middleware.ts — admin key guard**

```typescript
// web/middleware.ts
import { NextRequest, NextResponse } from "next/server"

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/admin")) {
    const key = request.nextUrl.searchParams.get("key")
    if (key !== "demo2026") {
      return new NextResponse("Unauthorized", { status: 401 })
    }
  }
  return NextResponse.next()
}

export const config = { matcher: ["/admin/:path*"] }
```

- [ ] **Step 3: Write app/layout.tsx**

```typescript
// web/app/layout.tsx
import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Career Lighthouse",
  description: "Locally-optimized AI career advisor",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  )
}
```

```css
/* web/app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: Create page stubs (so Next.js builds)**

```bash
mkdir -p web/app/admin web/app/student
echo 'export default function AdminPage() { return <div>Admin</div> }' > web/app/admin/page.tsx
echo 'export default function StudentPage() { return <div>Student</div> }' > web/app/student/page.tsx
```

- [ ] **Step 5: Verify build**

```bash
cd web && npm run build
# Expected: Build succeeded, no TypeScript errors
```

- [ ] **Step 6: Commit**

```bash
cd ..
git add web/
git commit -m "feat: Next.js scaffold with admin key middleware"
```

---

## Task 10: Web — Admin Page (Knowledge Upload + Doc List + Brief Generator)

**Files:**
- Create: `web/components/admin/KnowledgeUpload.tsx`
- Create: `web/components/admin/DocList.tsx`
- Create: `web/components/admin/BriefGenerator.tsx`
- Modify: `web/app/admin/page.tsx`

- [ ] **Step 1: Write KnowledgeUpload component**

```typescript
// web/components/admin/KnowledgeUpload.tsx
"use client"
import { useState } from "react"

interface Props { onUploaded: () => void }

export default function KnowledgeUpload({ onUploaded }: Props) {
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState("")
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    const files = Array.from(e.dataTransfer.files)
    if (!files.length) return
    setUploading(true)
    setMessage("")
    for (const file of files) {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${apiUrl}/api/ingest`, { method: "POST", body: form })
      const data = await res.json()
      setMessage(prev => prev + `✓ ${file.name} (${data.chunk_count} chunks)\n`)
    }
    setUploading(false)
    onUploaded()
  }

  async function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    setMessage("")
    for (const file of files) {
      const form = new FormData()
      form.append("file", file)
      const res = await fetch(`${apiUrl}/api/ingest`, { method: "POST", body: form })
      const data = await res.json()
      setMessage(prev => prev + `✓ ${file.name} (${data.chunk_count} chunks)\n`)
    }
    setUploading(false)
    onUploaded()
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Upload Knowledge</h2>
      <div
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
      >
        <p className="text-gray-500 mb-2">Drag & drop files here</p>
        <p className="text-sm text-gray-400">PDF, DOCX, TXT accepted</p>
        <input type="file" multiple accept=".pdf,.docx,.txt" className="hidden" id="file-input" onChange={handleFileInput} />
        <label htmlFor="file-input" className="mt-3 inline-block px-4 py-2 bg-blue-600 text-white rounded cursor-pointer text-sm">
          Browse Files
        </label>
      </div>
      {uploading && <p className="mt-2 text-sm text-blue-600">Uploading…</p>}
      {message && <pre className="mt-2 text-sm text-green-700 whitespace-pre-wrap">{message}</pre>}
    </div>
  )
}
```

- [ ] **Step 2: Write DocList component**

```typescript
// web/components/admin/DocList.tsx
"use client"
import { useEffect, useState } from "react"

interface Doc { doc_id: string; filename: string; chunk_count: number; uploaded_at: string }
interface Props { refreshKey: number }

export default function DocList({ refreshKey }: Props) {
  const [docs, setDocs] = useState<Doc[]>([])
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  useEffect(() => {
    fetch(`${apiUrl}/api/docs`).then(r => r.json()).then(setDocs)
  }, [refreshKey])

  async function handleDelete(docId: string) {
    await fetch(`${apiUrl}/api/docs/${encodeURIComponent(docId)}`, { method: "DELETE" })
    setDocs(docs.filter(d => d.doc_id !== docId))
  }

  if (!docs.length) return <p className="text-sm text-gray-400 mt-4">No documents uploaded yet.</p>

  return (
    <div className="mt-4">
      <h3 className="text-sm font-medium text-gray-600 mb-2">Knowledge Base ({docs.length} documents)</h3>
      <ul className="space-y-1">
        {docs.map(doc => (
          <li key={doc.doc_id} className="flex items-center justify-between text-sm bg-white border rounded px-3 py-2">
            <span className="truncate">{doc.filename}</span>
            <span className="text-gray-400 mx-3">{doc.chunk_count} chunks</span>
            <button onClick={() => handleDelete(doc.doc_id)} className="text-red-500 hover:text-red-700 text-xs">✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 3: Write BriefGenerator component**

```typescript
// web/components/admin/BriefGenerator.tsx
"use client"
import { useState } from "react"

export default function BriefGenerator() {
  const [resume, setResume] = useState("")
  const [brief, setBrief] = useState("")
  const [loading, setLoading] = useState(false)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  async function handleGenerate() {
    if (!resume.trim()) return
    setLoading(true)
    setBrief("")
    const res = await fetch(`${apiUrl}/api/brief`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_text: resume }),
    })
    const data = await res.json()
    setBrief(data.brief)
    setLoading(false)
  }

  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">Student Brief Generator</h2>
      <textarea
        value={resume}
        onChange={e => setResume(e.target.value)}
        placeholder="Paste student resume text here…"
        className="w-full h-40 border rounded p-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      <button
        onClick={handleGenerate}
        disabled={loading || !resume.trim()}
        className="mt-2 px-5 py-2 bg-blue-600 text-white rounded disabled:opacity-50 text-sm"
      >
        {loading ? "Generating…" : "Generate Brief"}
      </button>
      {brief && (
        <div className="mt-4 bg-white border rounded p-4 text-sm whitespace-pre-wrap leading-relaxed">
          {brief}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Assemble admin page**

```typescript
// web/app/admin/page.tsx
"use client"
import { useState } from "react"
import KnowledgeUpload from "@/components/admin/KnowledgeUpload"
import DocList from "@/components/admin/DocList"
import BriefGenerator from "@/components/admin/BriefGenerator"

export default function AdminPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
      <p className="text-sm text-gray-500 mb-8">Career Office Dashboard</p>
      <div className="grid grid-cols-2 gap-8">
        <div>
          <KnowledgeUpload onUploaded={() => setRefreshKey(k => k + 1)} />
          <DocList refreshKey={refreshKey} />
        </div>
        <div>
          <BriefGenerator />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Build and verify**

```bash
cd web && npm run build
# Expected: no TypeScript errors
```

- [ ] **Step 6: Commit**

```bash
cd ..
git add web/components/admin/ web/app/admin/page.tsx
git commit -m "feat: admin page — knowledge upload, doc list, brief generator"
```

---

## Task 11: Web — Student Page (Resume Upload + Chat + Citations)

**Files:**
- Create: `web/components/student/ResumeUpload.tsx`
- Create: `web/components/student/ChatInterface.tsx`
- Create: `web/components/student/CitationBadge.tsx`
- Modify: `web/app/student/page.tsx`

- [ ] **Step 1: Write CitationBadge**

```typescript
// web/components/student/CitationBadge.tsx
interface Props { filename: string; excerpt: string }

export default function CitationBadge({ filename, excerpt }: Props) {
  return (
    <span title={excerpt} className="inline-block text-xs bg-blue-50 border border-blue-200 text-blue-700 rounded px-2 py-0.5 mr-1 cursor-help">
      📄 {filename}
    </span>
  )
}
```

- [ ] **Step 2: Write ResumeUpload**

```typescript
// web/components/student/ResumeUpload.tsx
"use client"
import { useState } from "react"

interface Props { onResume: (text: string) => void; hasResume: boolean }

export default function ResumeUpload({ onResume, hasResume }: Props) {
  const [text, setText] = useState("")
  const [mode, setMode] = useState<"idle" | "paste">("idle")

  function handlePaste() {
    if (text.trim()) { onResume(text.trim()); setMode("idle") }
  }

  if (hasResume) return (
    <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
      ✓ Resume loaded — advice is personalized
      <button onClick={() => onResume("")} className="ml-auto text-xs text-gray-400 hover:text-gray-600">Clear</button>
    </div>
  )

  return (
    <div className="text-sm">
      {mode === "idle" ? (
        <div className="flex items-center gap-3">
          <button onClick={() => setMode("paste")} className="px-3 py-1.5 border rounded text-blue-600 hover:bg-blue-50">
            + Add resume for personalized advice
          </button>
          <span className="text-gray-400">or skip for general advice</span>
        </div>
      ) : (
        <div>
          <textarea value={text} onChange={e => setText(e.target.value)}
            placeholder="Paste your resume text…"
            className="w-full h-32 border rounded p-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-400" />
          <div className="mt-1 flex gap-2">
            <button onClick={handlePaste} className="px-3 py-1.5 bg-blue-600 text-white rounded text-xs">Use this resume</button>
            <button onClick={() => setMode("idle")} className="px-3 py-1.5 text-gray-500 text-xs">Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Write ChatInterface**

```typescript
// web/components/student/ChatInterface.tsx
"use client"
import { useState, useRef, useEffect } from "react"
import CitationBadge from "./CitationBadge"

interface Message { role: "user" | "assistant"; content: string; citations?: { filename: string; excerpt: string }[] }
interface Props { resumeText: string }

export default function ChatInterface({ resumeText }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const apiUrl = process.env.NEXT_PUBLIC_API_URL

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  async function send() {
    const msg = input.trim()
    if (!msg || loading) return
    const history = messages.map(m => ({ role: m.role, content: m.content }))
    setMessages(prev => [...prev, { role: "user", content: msg }])
    setInput("")
    setLoading(true)
    try {
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, resume_text: resumeText || null, history }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: "assistant", content: data.response, citations: data.citations }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[600px]">
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <p className="text-gray-400 text-sm text-center mt-8">Ask me anything about careers at your school.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] ${m.role === "user" ? "bg-blue-600 text-white" : "bg-white border"} rounded-2xl px-4 py-3`}>
              <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100 flex flex-wrap gap-1">
                  {m.citations.map((c, j) => <CitationBadge key={j} filename={c.filename} excerpt={c.excerpt} />)}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border rounded-2xl px-4 py-3 text-sm text-gray-400">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="mt-4 flex gap-2">
        <input
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), send())}
          placeholder="Ask about career paths, interviews, firms…"
          className="flex-1 border rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()}
          className="px-5 py-2 bg-blue-600 text-white rounded-xl text-sm disabled:opacity-50">
          Send
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Assemble student page**

```typescript
// web/app/student/page.tsx
"use client"
import { useState, useEffect } from "react"
import ResumeUpload from "@/components/student/ResumeUpload"
import ChatInterface from "@/components/student/ChatInterface"

export default function StudentPage() {
  const [resumeText, setResumeText] = useState("")

  useEffect(() => {
    setResumeText(sessionStorage.getItem("resume_text") || "")
  }, [])

  function handleResume(text: string) {
    setResumeText(text)
    if (text) sessionStorage.setItem("resume_text", text)
    else sessionStorage.removeItem("resume_text")
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-1">Career Lighthouse</h1>
      <p className="text-sm text-gray-500 mb-4">Your school's career knowledge, on demand.</p>
      <div className="mb-4">
        <ResumeUpload onResume={handleResume} hasResume={!!resumeText} />
      </div>
      <ChatInterface resumeText={resumeText} />
    </div>
  )
}
```

- [ ] **Step 5: Build and verify**

```bash
cd web && npm run build
# Expected: success
```

- [ ] **Step 6: Commit**

```bash
cd ..
git add web/components/student/ web/app/student/page.tsx
git commit -m "feat: student page — resume upload, chat interface, citations"
```

---

## Task 12: Integration Smoke Test

**No new files.** Verify the full stack runs together.

- [ ] **Step 1: Create .env and start stack**

```bash
cp .env.example .env
# Edit .env: add your real ANTHROPIC_API_KEY
docker compose up --build
# Wait for both services to be healthy (~60-90s first build due to sentence-transformers download)
```

- [ ] **Step 2: Verify health endpoint**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

- [ ] **Step 3: Upload demo data**

```bash
for f in demo-data/*.txt; do
  curl -s -X POST http://localhost:8000/api/ingest \
    -F "file=@$f" | python3 -m json.tool
done
# Expected: each file returns {"doc_id": "...", "chunk_count": N, "status": "ok"}
```

- [ ] **Step 4: Verify doc list**

```bash
curl http://localhost:8000/api/docs | python3 -m json.tool
# Expected: array of 5 documents
```

- [ ] **Step 5: Test chat endpoint**

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I get into GIC from NUS?", "resume_text": null, "history": []}' \
  | python3 -m json.tool
# Expected: response with citations referencing gic-recruiting-guide.txt or nus-alumni-paths.txt
```

- [ ] **Step 6: Open UI and demo the full flow**

```
Admin:   http://localhost:3000/admin?key=demo2026
Student: http://localhost:3000/student
```

Walk through: upload a file → check doc list → switch to student → ask a question → verify citations appear → back to admin → paste a resume → generate brief.

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: integration smoke test passed, demo data loaded"
```

---

## Task 13: Terraform (AWS ap-southeast-1) — Optional, Post-Hackathon

**Files:**
- Create: `terraform/variables.tf`
- Create: `terraform/main.tf`
- Create: `terraform/outputs.tf`

This task is independent of all others. Build after the hackathon demo is working.

- [ ] **Step 1: Write variables.tf**

```hcl
# terraform/variables.tf
variable "aws_region" { default = "ap-southeast-1" }
variable "anthropic_api_key" { sensitive = true }
variable "app_name" { default = "career-lighthouse" }
variable "ecr_image_api" { description = "ECR image URI for API service" }
variable "ecr_image_web" { description = "ECR image URI for web service" }
```

- [ ] **Step 2: Write main.tf**

```hcl
# terraform/main.tf
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

# EFS for Qdrant persistent volume
resource "aws_efs_file_system" "qdrant" {
  encrypted = true
  tags = { Name = "${var.app_name}-qdrant" }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = var.app_name
}

# ECS Task Definition — API
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.app_name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"

  volume {
    name = "qdrant-data"
    efs_volume_configuration {
      file_system_id = aws_efs_file_system.qdrant.id
      root_directory = "/"
    }
  }

  container_definitions = jsonencode([{
    name  = "api"
    image = var.ecr_image_api
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "DATA_PATH", value = "/data/qdrant" },
      { name = "ALLOWED_ORIGINS", value = "https://${aws_amplify_app.web.default_domain}" }
    ]
    secrets = [
      { name = "ANTHROPIC_API_KEY", valueFrom = aws_ssm_parameter.anthropic_key.arn }
    ]
    mountPoints = [{ sourceVolume = "qdrant-data", containerPath = "/data/qdrant" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = "/ecs/${var.app_name}"
        "awslogs-region" = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}

# SSM Parameter for API key
resource "aws_ssm_parameter" "anthropic_key" {
  name  = "/${var.app_name}/anthropic_api_key"
  type  = "SecureString"
  value = var.anthropic_api_key
}

# Amplify for Next.js frontend
resource "aws_amplify_app" "web" {
  name = "${var.app_name}-web"
  environment_variables = {
    NEXT_PUBLIC_API_URL = "https://${aws_lb.api.dns_name}"
  }
}
```

- [ ] **Step 3: Write outputs.tf**

```hcl
# terraform/outputs.tf
output "api_url" { value = "https://${aws_lb.api.dns_name}" }
output "web_url" { value = "https://${aws_amplify_app.web.default_domain}" }
output "efs_id"  { value = aws_efs_file_system.qdrant.id }
```

- [ ] **Step 4: Commit**

```bash
git add terraform/
git commit -m "feat: Terraform templates for AWS ap-southeast-1 deployment"
```

---

## Summary

| Task | What it builds | Tests |
|------|---------------|-------|
| 1 | Repo + demo data | — |
| 2 | Docker + compose | Manual |
| 3 | API skeleton + models | pytest (0 tests) |
| 4 | Embedder service | 3 unit tests |
| 5 | Vector store (Qdrant) | 3 unit tests |
| 6 | Ingestion service | 4 unit tests |
| 7 | LLM service | — (mocked in router tests) |
| 8 | All API routers | 6 router tests |
| 9 | Next.js scaffold + middleware | Build check |
| 10 | Admin page (upload/docs/brief) | Build check |
| 11 | Student page (chat/citations) | Build check |
| 12 | Integration smoke test | Manual e2e |
| 13 | Terraform (optional) | Manual |

**Demo script (5 min):**
1. `docker compose up` → show both services healthy
2. Open `/admin?key=demo2026` → drag in `gic-recruiting-guide.txt` → show doc list
3. Open `/student` → paste a resume → ask "How do I get into GIC?" → show citation badge pointing to the uploaded doc
4. Back to `/admin` → paste same resume → Generate Brief → show counselor pre-meeting summary
5. "This is the only tool where the advice comes from *your* career office. No data leaves your server."
