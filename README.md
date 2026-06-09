# Enterprise Data Copilot

Production-oriented AI chatbot for asking natural language questions over live PostgreSQL business data and company policy documents.

The system supports questions such as:

- `committed quantity of PO1001`
- `Who is supplier of PO1001?`
- `Available stock of material MAT0006`
- `Show top 5 customers by order quantity`
- `What is the reimbursement limit for meals?`

## High-Level Architecture

```text
User
  -> React + TypeScript Frontend
  -> Django REST API
       -> Authentication
       -> JWT refresh/session management
       -> Admin panel
       -> Business tables
  -> FastAPI AI Service
       -> Intent router
       -> Redis semantic cache
       -> LangGraph database workflow
       -> Policy RAG workflow
  -> PostgreSQL
  -> Redis
  -> Elasticsearch
  -> Local/Ops LLM provider
```

## Technology Stack

| Area | Technology | Purpose |
| --- | --- | --- |
| Frontend | React, TypeScript, TailwindCSS, Vite | Chat UI, session sidebar, answer details, SQL/result inspection |
| Auth/API | Django, Django REST Framework | Login, refresh tokens, user management, admin panel |
| AI API | FastAPI | Chatbot endpoints, policy RAG, SQL agent endpoints |
| Database | PostgreSQL | Live business data, chat records, audit logs, users |
| Cache/State | Redis | Semantic cache, chat memory, rate limits, refresh tokens, LangGraph state |
| Search/RAG | Elasticsearch | Schema metadata retrieval and policy document vector/keyword search |
| Agent Runtime | LangGraph, LangChain | Stateful tool-calling workflow |
| LLM Runtime | Ollama, optional Gemini | Reasoning, SQL generation, policy answer generation |
| Embeddings | `nomic-embed-text` | Semantic cache and policy vector retrieval |
| Deployment | Docker, Docker Compose | Local infrastructure and containerized services |

## Main Components

### Django REST API

Django is responsible for the application backend concerns:

- User authentication
- JWT access and refresh tokens
- Password hashing through Django auth
- Admin panel for business tables
- Business database models
- Chat session and message persistence
- Audit log persistence

Important local endpoints:

```text
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
POST /api/v1/auth/logout/
GET  /api/v1/auth/me/
GET  /admin/
```

### FastAPI AI Service

FastAPI exposes the AI-facing endpoints:

```text
POST   /api/v1/ask/
GET    /api/v1/chat/sessions
GET    /api/v1/chat/sessions/{session_id}
DELETE /api/v1/chat/sessions/{session_id}
PATCH  /api/v1/chat/sessions/{session_id}/title
POST   /api/v1/policies/search
GET    /api/v1/policies/documents
POST   /api/v1/policies/documents/upload
POST   /api/v1/policies/documents/reindex
DELETE /api/v1/policies/documents/{filename}
GET    /api/v1/workflows/{workflow_run_id}
```

## Why Elasticsearch Is Used

Elasticsearch is not used as the transactional database.

It is used for retrieval:

1. **Business schema metadata retrieval**

   The SQL agent does not rely only on the LLM guessing table and column names. Schema metadata is indexed into Elasticsearch with business-friendly descriptions.

   Example:

   ```json
   {
     "table": "purchase_order_items",
     "column": "commit_qty",
     "business_name": "Committed Quantity",
     "description": "Quantity committed by supplier for a purchase order line."
   }
   ```

   Before SQL generation, the AI service searches Elasticsearch for relevant schema metadata and passes it into the SQL generation prompt.

2. **Policy document RAG**

   Company policy documents are chunked, embedded, and indexed into Elasticsearch.

   For policy questions, Elasticsearch retrieves relevant document chunks. The LLM then answers using only those retrieved chunks and returns citations.

3. **Hybrid retrieval**

   Policy search uses Elasticsearch hybrid retrieval. It does not depend on only one search method.

   ```text
   User policy question
     -> Generate question embedding with nomic-embed-text
     -> Elasticsearch vector search over policy chunk embeddings
     -> Elasticsearch keyword/BM25 search over policy title and text
     -> Reciprocal rank fusion merges both result lists
     -> Top ranked chunks are sent to the LLM
     -> LLM returns an answer with citations
   ```

   The hybrid search has three parts:

   - **Vector search**

     The user question is converted into an embedding using `nomic-embed-text`. Elasticsearch compares that vector with stored policy chunk vectors. This finds semantically similar chunks even when the user does not use the exact same words as the policy document.

     Example: `meal allowance` can still match a chunk containing `Meal reimbursement is capped at 60 USD per day`.

   - **Keyword/BM25 search**

     Elasticsearch also runs a keyword search over `document_title` and `text`. This is useful for exact terms, acronyms, policy names, and compliance words.

     Example: `VPN`, `MFA`, `receipt`, `reimbursement`, and `restricted data`.

   - **Reciprocal rank fusion**

     Vector search and keyword search return separate ranked lists. Reciprocal rank fusion combines those lists into one final ranking. A chunk that appears high in both lists becomes stronger. A chunk that appears high in only one list can still be selected if it is highly relevant.

   This gives better retrieval quality than vector-only or keyword-only search.

## Hybrid Intent Detection

The chatbot supports both live database questions and policy document questions.

The intent router uses a hybrid multi-stage technique:

1. **Entity pattern rules**

   If the question contains business entity codes like `PO1001`, `MAT0006`, `CUST00003`, `SO1001`, or `SUP0001`, it is treated as a database question.

2. **Keyword scoring**

   Policy keywords such as `reimbursement`, `travel`, `VPN`, `receipt`, `remote work`, and `data security` indicate policy intent.

   Database keywords such as `supplier`, `stock`, `material`, `invoice`, `shipment`, and `quantity` indicate database intent.

3. **Embedding similarity**

   The question is embedded and compared with curated examples for database and policy questions.

4. **Optional LLM fallback**

   If enabled, the LLM can classify ambiguous questions.

5. **Default**

   If no strong policy intent is found, the system defaults to live database mode.

This is better than using only an LLM classifier because it is faster, cheaper, more predictable, and easier to debug.

## Redis Responsibilities

Redis is a core runtime dependency, not just a cache.

It is used for:

1. **Chat memory**

   Recent user and assistant messages are stored per chat session for quick context retrieval.

2. **Semantic cache**

   For database questions, the system stores:

   - Original question
   - Question embedding
   - Generated SQL
   - Final answer
   - Timestamp

   Before running the LangGraph workflow, the AI service embeds the new question and checks Redis for a semantically similar cached answer. If similarity is high enough, the system returns the cached answer and skips SQL generation and LLM calls.

3. **Session management**

   Login sessions and refresh-token mappings are stored in Redis.

4. **Rate limiting**

   FastAPI uses Redis to enforce user-based rate limits.

5. **LangGraph state**

   Workflow runs, checkpoints, node statuses, generated SQL, execution results, and final state are stored in Redis so workflow traces can be inspected later.

## Database Workflow

```text
User question
  -> JWT authentication
  -> Rate limit check
  -> Intent router decides database
  -> Redis semantic cache lookup
  -> Chat history context retrieval
  -> Elasticsearch schema metadata retrieval
  -> LLM SQL generation
  -> SQL validation
  -> Safe SQL execution against PostgreSQL
  -> LLM answer summarization
  -> Redis semantic cache write
  -> Chat message persistence
  -> Audit log write
  -> API response
```

SQL validation allows only read-only `SELECT` statements and blocks dangerous operations such as:

- `DELETE`
- `UPDATE`
- `INSERT`
- `DROP`
- `ALTER`
- `TRUNCATE`
- Multiple statements
- Comment-based bypass attempts
- Sleep/delay functions

## Policy RAG Workflow

```text
User question
  -> JWT authentication
  -> Rate limit check
  -> Intent router decides policy
  -> Elasticsearch hybrid policy search
       -> Vector search
       -> Keyword search
       -> Reciprocal rank fusion
  -> Score threshold filtering
  -> LLM answer generation using retrieved chunks
  -> Citations returned
  -> Chat message persistence
  -> Audit log write
  -> API response
```

Policy answers include:

- Natural language answer
- Policy source chunks
- Citations
- Document id
- Document title
- Source path
- Chunk id
- Chunk score

## Security Features

Implemented security controls include:

- JWT authentication
- Refresh token support
- Redis-backed refresh token/session tracking
- Password hashing through Django authentication
- Staff-only access for metadata, SQL tools, and policy admin endpoints
- User ownership enforcement for chat sessions
- User ownership enforcement for workflow traces
- User-based Redis rate limiting
- SQL validation before execution
- Read-only SQL execution
- SQL execution timeout
- SQL result limits
- Dangerous SQL keyword blocking
- API input validation using Pydantic
- Django model constraints and indexes
- Audit logging for AI asks and policy document admin actions
- CORS allowlist for the frontend origin
- Docker non-root runtime user for the AI service container
- `.dockerignore` excludes local secrets such as `.env`

## Observability

The project includes structured logging for:

- Request flow
- Intent decisions
- Metadata retrieval
- SQL generation
- SQL validation
- SQL execution
- Policy retrieval
- Semantic cache hits/misses
- Chat persistence
- Audit log writes
- LangGraph checkpoints

Workflow traces can be inspected through:

```text
GET /api/v1/workflows/{workflow_run_id}
```

## Local Setup

### 1. Start infrastructure

```bash
docker compose up -d
```

Verify Redis:

```bash
docker exec enterprise-data-copilot-redis redis-cli ping
```

Verify Elasticsearch:

```bash
curl "http://localhost:9200/_cluster/health?pretty"
```

### 2. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Update secrets and database values in `.env`.

### 4. Run Django migrations

```bash
python manage.py migrate
```

### 5. Seed demo data

```bash
python manage.py seed_demo_data
```

### 6. Index schema metadata

```bash
python manage.py index_schema_metadata --reset
```

### 7. Index policy documents

```bash
python manage.py index_policy_documents --reset
```

### 8. Start Django API

```bash
python manage.py runserver 8000
```

### 9. Start FastAPI AI service

```bash
python -m uvicorn backend.ai_service.main:app --reload --port 8001
```

### 10. Start frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Example Test Questions

Database questions:

```text
Available stock of material MAT0006
committed quantity of PO1001
Who is supplier of PO1001?
Show top 5 customers by order quantity
Which supplier created the highest number of orders this month?
```

Policy questions:

```text
What is the reimbursement limit for meals?
Can employees work remotely three days per week?
What data must not be shared in chat or email?
What expenses are not reimbursable?
When should suspected data incidents be reported?
```

## Useful API Commands

Login:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'
```

Ask:

```bash
curl -X POST http://127.0.0.1:8001/api/v1/ask/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -d '{"question":"Available stock of material MAT0006","limit":3}'
```

Search policy chunks:

```bash
curl -X POST http://127.0.0.1:8001/api/v1/policies/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -d '{"query":"What is the reimbursement limit for meals?","limit":3}'
```

List chat sessions:

```bash
curl http://127.0.0.1:8001/api/v1/chat/sessions \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

## Project Structure

```text
backend/
  django_app/
    authentication/
    config/
    core/
    health/
  ai_service/
    api/
    schemas/
    security/
    services/
  shared/
frontend/
  src/
data/
  company_policies/
docs/
requirements/
tests/
```

## Current Status

Implemented:

- Docker Compose infrastructure for PostgreSQL, Redis, Elasticsearch
- Django models and admin panel
- Demo business data generation
- JWT authentication and refresh tokens
- FastAPI AI service
- Dynamic SQL generation and validation
- LangGraph workflow state in Redis
- Redis semantic cache
- Redis chat memory
- Policy document RAG using Elasticsearch
- Hybrid intent router
- Policy document upload/reindex/delete APIs
- Chat session list/detail/archive/rename APIs
- React frontend first UI
- Audit logging
- Structured logging
- AI service Dockerfile

Still planned:

- Full production frontend authentication flow
- Dockerfiles for Django and frontend
- CI pipeline
- Deployment manifests
- More advanced monitoring dashboards
