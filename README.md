# DocuMind — Enterprise RAG Platform

> Chat with your documents using AI. Upload PDFs, DOCX, TXT files, and images — then ask questions in natural language. DocuMind finds the exact relevant sections and answers from them. No hallucination.

<div align="center">

**[🌐 Live Demo](https://documind-enterprise-grade-rag.vercel.app/)** &nbsp;·&nbsp; **

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-00B5AD?style=flat-square)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat-square&logo=supabase&logoColor=white)
![Deployed on Vercel](https://img.shields.io/badge/Vercel-Frontend-000000?style=flat-square&logo=vercel&logoColor=white)
![Deployed on Render](https://img.shields.io/badge/Render-Backend-46E3B7?style=flat-square)

</div>

---

## What is DocuMind

DocuMind is a production-grade multi-user platform that lets people upload documents and chat with them using AI. Unlike simple RAG tutorials, this is built with the full stack a real product needs — authentication, vector search, streaming responses, caching, rate limiting, LLM failover, and image understanding.

**The problem it solves:** Reading through large documents to find specific information is slow and inefficient. DocuMind lets you ask plain English questions and get precise, cited answers in seconds.

**What makes it production-grade:**
- Every user's documents are completely isolated from others using Pinecone namespaces
- Azure OpenAI silently fails over to Groq Llama 3.3 70B if it goes down — users never notice
- Redis caches repeated answers so popular questions respond instantly with zero LLM cost
- Images and charts inside PDFs are understood using multi-modal GPT-4o and made searchable
- Per-user rate limiting prevents any single user from draining the API quota

---

## Features

### Document Intelligence
- **Multi-format ingestion** — PDF, DOCX, TXT, JPG, PNG, WEBP
- **Image understanding** — charts, diagrams, and images inside PDFs are described by GPT-4o and made fully searchable
- **Standalone image uploads** — upload a screenshot or photo and chat with it
- **Smart chunking** — overlapping fixed-size chunks with sentence-boundary detection
- **Source citations** — every answer shows which document it came from

### AI & RAG
- **Semantic vector search** — Azure text-embedding-3-large (3072 dimensions) for high-precision retrieval
- **Intent detection** — greetings and small talk answered directly, document questions routed through RAG
- **Summary handling** — "summarise the document" triggers a broad multi-query retrieval across the full document
- **Reranker slot** — architecture ready for Cohere or cross-encoder reranker 
- **Chat memory** — last 6 turns of conversation injected so follow-up questions work naturally

### Infrastructure
- **Real-time streaming** — answers stream token by token via Server-Sent Events
- **LLM failover** — GPT-4o  → Groq Llama 3.3 70B, automatic and silent
- **Answer caching** — Redis stores answers for 1 hour, repeated questions return instantly
- **Rate limiting** — per-user sliding window counter via Redis (configurable requests/minute)
- **Multi-user isolation** — each user's vectors live in their own Pinecone namespace

### Security & Auth
- **Supabase Auth** — JWT-based authentication, email verification, secure password hashing
- **Row-level security** — PostgreSQL RLS policies ensure users can only access their own data
- **Token validation** — every API endpoint validates the JWT before processing
- **Error handling** — global exception handler never leaks stack traces to clients

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────────────┐
│              VERCEL — React Frontend (CDN)                      │
│   Login/Signup · Document Sidebar · Chat UI · SSE Streaming     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST + SSE
┌─────────────────────────▼───────────────────────────────────────┐
│              RENDER — FastAPI Backend (Python 3.11)             │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  Auth       │  │  Documents   │  │  Chat                 │  │
│  │  /signup    │  │  /upload     │  │  /stream (SSE)        │  │
│  │  /login     │  │  /list       │  │  /sessions            │  │
│  │  /logout    │  │  /delete     │  │  /history             │  │
│  └─────────────┘  └──────────────┘  └───────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Services Layer                        │   │
│  │                                                          │   │
│  │  IngestionService          RAGService                    │   │
│  │  ├── parse (PDF/DOCX/TXT)  ├── embed question           │   │
│  │  ├── extract images        ├── search Pinecone           │   │
│  │  ├── vision description    ├── [reranker slot]           │   │
│  │  ├── chunk text            ├── build prompt              │   │
│  │  └── embed + upsert        └── stream answer             │   │
│  │                                                          │   │
│  │  LLMService                CacheService                  │   │
│  │  ├── Azure GPT-4o mini     ├── rate limit check          │   │
│  │                            ├── answer cache get/set      │   │
│  │  └── Groq fallback         └── cache invalidation        │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────┬──────────────────┬──────────────────┬────────────────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼───────┐  ┌──────▼──────────────────┐
│  PINECONE   │  │   SUPABASE     │  │  UPSTASH REDIS           │
│             │  │                │  │                          │
│ Vector DB   │  │ PostgreSQL     │  │ Answer cache (1hr TTL)   │
│ Per-user    │  │ ├── documents  │  │ Rate limit counters      │
│ namespaces  │  │ ├── sessions   │  │ (60s sliding window)     │
│ 3072 dims   │  │ └── messages   │  │                          │
└─────────────┘  │ Auth (JWT)     │  └──────────────────────────┘
                 │ Row-level sec  │
                 └────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      AI PROVIDERS                               │
│                                                                 │
│  Azure OpenAI (Primary)          Groq (Fallback)               │
│  ├── GPT-4o mini (inference)     └── Llama 3.3 70B             │
│  ├── GPT-4o (vision)                 (automatic failover)      │
│  └── text-embedding-3-large                                     │
│       (3072 dimensions)                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Upload flow

```
User uploads file
      │
      ▼
FastAPI validates (type + size)
      │
      ├── PDF/DOCX/TXT ──► parse text ──────────────────────────┐
      │                                                          │
      └── PDF with images ──► extract images                    │
                │                   │                           │
                │                   ▼                           │
                │         GPT-4o vision description             │
                │                   │                           │
                └───────────────────┘                           │
                                    │                           │
                                    ▼                           │
                             chunk text (2000 chars,            │
                             200 char overlap)                  │
                                    │                           │
                                    ▼                           │
                    text-embedding-3-large (3072d) ◄────────────┘
                                    │
                                    ▼
                    Pinecone upsert (namespace = user-{id})
                                    │
                                    ▼
                    Supabase: save document record
```

### Query flow

```
User types question
      │
      ▼
Is it conversational? (string match)
      ├── YES ──► LLM direct answer (no vector search)
      │
      └── NO
            │
            ▼
      Is it a summary request?
            ├── YES ──► broad multi-query retrieval (10 chunks)
            │                across full document range
            └── NO
                  │
                  ▼
            Redis cache check
                  ├── HIT  ──► return instantly (0 LLM cost)
                  │
                  └── MISS
                        │
                        ▼
                  Rate limit check (Redis counter)
                        │
                        ▼
                  Embed question (text-embedding-3-large)
                        │
                        ▼
                  Pinecone search (user namespace, top 10)
                        │
                        ▼
                  [Reranker slot — passthrough now,
                   Cohere/cross-encoder drops in here]
                        │
                        ▼
                  Take top 5 chunks
                        │
                        ▼
                  Build prompt (system + history + context + question)
                        │
                        ▼
                  Azure GPT-4o mini ──► (if fails) ──► Groq Llama 3.3
                        │
                        ▼
                  Stream tokens via SSE ──► React UI
                        │
                        ▼
                  Save to Redis cache + Supabase history
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 18 + Vite | UI framework |
| Styling | Tailwind CSS | Utility-first styling |
| State | Zustand | Global auth + document state |
| Routing | React Router v6 | Client-side routing |
| HTTP | Axios + Fetch API | REST calls + SSE streaming |
| Backend | FastAPI (Python 3.11) | Async API framework |
| Auth | Supabase Auth | JWT tokens, email verification |
| Relational DB | Supabase PostgreSQL | Documents, sessions, messages |
| Vector DB | Pinecone | Semantic search (3072 dimensions) |
| Cache | Upstash Redis | Answer cache + rate limiting |
| Primary LLM | Azure GPT-4o mini | Inference + chat |
| Vision LLM | Azure GPT-4o | Image + chart understanding |
| Fallback LLM | Groq Llama 3.3 70B | Automatic LLM failover |
| Embeddings | Azure text-embedding-3-large | 3072-dimension vectors |
| PDF parsing | pymupdf | Text + image extraction |
| Logging | Loguru | Structured JSON logs |
| Frontend host | Vercel | Global CDN, auto-deploy |
| Backend host | Render | Python hosting, auto-deploy |
| CI/CD | GitHub → Vercel + Render | Push-to-deploy |

---

## Project Structure

```
documind/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, routes
│   │   ├── api/
│   │   │   ├── dependencies.py      # JWT validation, shared Supabase client
│   │   │   └── routes/
│   │   │       ├── auth.py          # signup, login, logout
│   │   │       ├── documents.py     # upload, list, delete
│   │   │       ├── chat.py          # SSE streaming, session history
│   │   │       └── admin.py         # usage stats
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings, env loading
│   │   │   └── logging.py           # Loguru structured logging
│   │   ├── services/
│   │   │   ├── llm_service.py       # Azure + Groq, streaming
│   │   │   ├── ingestion_service.py # parse → chunk → embed → upsert
│   │   │   ├── rag_service.py       # retrieve → rerank → prompt → stream
│   │   │   └── cache_service.py     # Redis rate limiting + answer cache
│   │   ├── models/                  # SQLAlchemy models (future migrations)
│   │   └── middleware/              # Auth guard, rate limiter hooks
│   ├── requirements.txt
│   ├── .env.example
│   └── Procfile                     # Render start command
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Router, protected routes
│   │   ├── pages/
│   │   │   ├── Login.jsx            # Auth form, dark glassy UI
│   │   │   ├── Signup.jsx           # Registration with validation
│   │   │   └── Dashboard.jsx        # Main layout, state orchestration
│   │   ├── components/
│   │   │   ├── Sidebar.jsx          # Document list, upload, user footer
│   │   │   ├── ChatPanel.jsx        # SSE streaming, message rendering
│   │   │   └── MarkdownRenderer.jsx # Custom markdown without react-markdown
│   │   ├── store/
│   │   │   ├── authStore.js         # Zustand auth state
│   │   │   └── documentStore.js     # Zustand document state
│   │   └── api/
│   │       └── client.js            # Axios with JWT interceptor
│   ├── vercel.json                  # SPA rewrite rules
│   └── .env.production              # VITE_API_URL for Vercel
│
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Accounts on: [Pinecone](https://pinecone.io), [Supabase](https://supabase.com), [Upstash](https://upstash.com), [Groq](https://console.groq.com)
- Azure OpenAI resource with GPT-4o mini and text-embedding-3-large deployed

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/documind.git
cd documind
```



## API Reference

Full interactive docs at `https://your-api.onrender.com/api/docs`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/signup` | No | Create account |
| POST | `/api/auth/login` | No | Login, returns JWT |
| POST | `/api/auth/logout` | No | Sign out |
| POST | `/api/documents/upload` | Yes | Upload + ingest document |
| GET | `/api/documents/` | Yes | List user's documents |
| DELETE | `/api/documents/{id}` | Yes | Delete document + vectors |
| POST | `/api/chat/stream` | Yes | Stream RAG answer (SSE) |
| GET | `/api/chat/sessions` | Yes | List chat sessions |
| GET | `/api/chat/sessions/{id}/messages` | Yes | Get session messages |
| GET | `/api/admin/stats` | Yes | Usage statistics |
| GET | `/api/health` | No | Health check |

### Chat stream request body

```json
{
  "question": "What is the refund policy?",
  "session_id": "uuid-optional-for-history",
  "document_ids": ["uuid1", "uuid2"]
}
```

`document_ids` is optional — omit it to search across all user documents.

### SSE response format

```
data: {"token": "The"}
data: {"token": " refund"}
data: {"token": " policy"}
...
data: [DONE]
```

---

## Deployment

### Backend → Render

1. Connect GitHub repo to [render.com](https://render.com)
2. New Web Service → Root Directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add all environment variables from `.env`
6. Health check path: `/api/health`

### Frontend → Vercel

1. Connect GitHub repo to [vercel.com](https://vercel.com)
2. Root Directory: `frontend`
3. Framework: Vite (auto-detected)
4. Add environment variable: `VITE_API_URL=https://your-api.onrender.com`
5. Deploy

Every `git push` to `main` triggers automatic redeploy on both platforms.

---



## Author

Built by  Debdoot Sen



---

*Built with FastAPI, React, Pinecone, Supabase, Azure OpenAI, and a lot of debugging.*
