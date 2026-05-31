# Step 2 - PostgreSQL Infrastructure

## Objective

Add PostgreSQL as the transactional database for the enterprise chatbot platform.

This step only creates the PostgreSQL container infrastructure. It does not create schemas, demo data, Django, FastAPI, LangGraph, or React code.

## Architecture

PostgreSQL will be the source of truth for business and application data.

Future responsibilities:

- Business master data such as customers, suppliers, and materials
- Transactional data such as purchase orders, sales orders, shipments, and invoices
- Application data such as users, chat sessions, chat messages, and audit logs
- Read-only SQL execution target for validated chatbot queries

Redis and Elasticsearch remain separate services:

- Redis handles session state, chat history cache, semantic cache, rate limiting, and future LangGraph checkpoints.
- Elasticsearch handles business metadata search, not transactional data.

## Architectural Decisions

- `postgres:16-alpine` is used because PostgreSQL 16 is stable and production proven, while the Alpine image keeps the local container lightweight.
- Credentials are supplied through environment variables so secrets can later be moved to a secret manager or deployment environment.
- A named Docker volume stores database files outside the container lifecycle.
- `pg_isready` is used for the health check because it verifies that PostgreSQL is accepting connections.
- Schema and seed data are intentionally deferred to a later step to keep this step independently reviewable.

## Folder Structure Changes

```text
enterprise-data-copilot/
  .env.example
  .gitignore
  docker-compose.yml
  PROJECT_REQUIREMENTS.md
  docs/
    STEP_01_REDIS_ELASTICSEARCH.md
    STEP_02_POSTGRESQL.md
```

## Complete PostgreSQL Compose Service

```yaml
postgres:
  image: postgres:16-alpine
  container_name: enterprise-data-copilot-postgres
  environment:
    POSTGRES_DB: ${POSTGRES_DB:-enterprise_data_copilot}
    POSTGRES_USER: ${POSTGRES_USER:-enterprise_app}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-enterprise_app_password}
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test:
      [
        "CMD-SHELL",
        "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"
      ]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 10s
  restart: unless-stopped
```

## Environment Setup

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

For local development, you may keep the example values. Before any shared or production deployment, change the password.

## Pull PostgreSQL Image

```bash
docker pull postgres:16-alpine
```

## Start Infrastructure

From the project root:

```bash
docker compose up -d
```

## Check Containers

```bash
docker compose ps
```

Expected result:

```text
enterprise-data-copilot-postgres         healthy
enterprise-data-copilot-redis            healthy
enterprise-data-copilot-elasticsearch    healthy
```

## Verify PostgreSQL Connectivity

```bash
docker exec enterprise-data-copilot-postgres pg_isready -U enterprise_app -d enterprise_data_copilot
```

Expected output:

```text
/var/run/postgresql:5432 - accepting connections
```

Run a SQL smoke test:

```bash
docker exec enterprise-data-copilot-postgres psql -U enterprise_app -d enterprise_data_copilot -c "SELECT version();"
```

Expected output includes:

```text
PostgreSQL 16
```

## Verify Persistent Volume

```bash
docker volume ls
```

Expected volume:

```text
enterprise-data-copilot_postgres_data
```

Inspect the volume:

```bash
docker volume inspect enterprise-data-copilot_postgres_data
```

## Stop Infrastructure

```bash
docker compose down
```

## Stop And Delete Data

Use this only when you intentionally want a clean database reset:

```bash
docker compose down -v
```

## Expected Step 2 Outcome

At the end of this step:

- Redis is running and healthy.
- Elasticsearch is running and healthy.
- PostgreSQL is running and healthy.
- PostgreSQL has persistent local storage.
- No application code has been created yet.
