# Enterprise Data Copilot - Project Requirements

## Goal

Build a production-grade conversational chatbot that answers natural language questions from live PostgreSQL business data.

## Architecture

```text
User
  -> React Frontend
  -> Django REST API
  -> FastAPI AI Layer
  -> LangGraph Agent
  -> Tools: Metadata Retrieval, SQL Generation, SQL Validation, SQL Execution, Chat History
  -> PostgreSQL, Elasticsearch, Redis
```

## Core Technology Stack

- Backend API: Python, Django, Django REST Framework
- AI service: FastAPI
- Database: PostgreSQL
- Metadata search: Elasticsearch
- Cache/session/state: Redis
- AI orchestration: LangGraph, LangChain
- LLM runtime: local Ollama
- LLM models:
  - Reasoning: `qwen2.5:14b`
  - SQL generation: `qwen2.5-coder:14b-instruct`
  - Optional smaller SQL model: `qwen2.5-coder:7b-instruct`
  - Embeddings: `nomic-embed-text`
- Frontend: React, TypeScript, TailwindCSS
- Auth: JWT authentication with refresh tokens
- Deployment: Docker, Docker Compose

## Redis Responsibilities

- Chat history storage per user session
- Semantic cache using question embeddings, generated SQL, final answers, and timestamps
- Session management
- Refresh token storage
- User-based rate limiting
- LangGraph checkpoints and conversation state

## Elasticsearch Responsibilities

Elasticsearch stores metadata only, not transactional business data.

Example metadata document:

```json
{
  "table": "purchase_orders",
  "column": "commit_qty",
  "business_name": "Committed Quantity",
  "description": "Committed quantity of purchase order"
}
```

## PostgreSQL Responsibilities

PostgreSQL stores transactional business data, application users, chat session records, chat message records, and audit logs.

The production application must access PostgreSQL through least-privilege application credentials and must validate generated SQL before execution.

## Database Tables To Build Later

- users
- customers
- suppliers
- materials
- inventory
- purchase_orders
- purchase_order_items
- sales_orders
- sales_order_items
- order_schedule
- shipment
- invoice
- chat_sessions
- chat_messages
- audit_logs

## Step 1 Scope

This step creates only local infrastructure for Redis and Elasticsearch.

Included:

- Docker Desktop requirement documentation
- Redis Docker image
- Elasticsearch Docker image
- Docker Compose file
- Persistent Docker volumes
- Container health checks
- Redis connectivity verification
- Elasticsearch connectivity verification

Excluded:

- Django
- FastAPI
- PostgreSQL
- LangGraph implementation
- React frontend

## Step 2 Scope

This step adds only PostgreSQL infrastructure.

Included:

- PostgreSQL Docker image
- Docker Compose PostgreSQL service
- Persistent PostgreSQL volume
- PostgreSQL health check
- Environment variable template
- Connectivity verification commands

Excluded:

- Database schema creation
- Demo data generation
- Django
- FastAPI
- LangGraph implementation
- React frontend
