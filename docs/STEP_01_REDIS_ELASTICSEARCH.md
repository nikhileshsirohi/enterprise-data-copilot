# Step 1 - Redis and Elasticsearch Infrastructure

## Objective

Install and run Redis and Elasticsearch locally using Docker Compose.

This step does not create Django, FastAPI, PostgreSQL, LangGraph, or React code.

## Architectural Decision

Redis and Elasticsearch are containerized with Docker Compose because the application will eventually need repeatable local development and deployment-ready infrastructure.

Redis uses append-only persistence so chat history, semantic cache entries, sessions, rate limit counters, and future LangGraph state can survive container restarts.

Elasticsearch uses a persistent named volume and runs as a single-node development cluster. Security is disabled for local development only. In production, Elasticsearch security, TLS, users, and secrets must be enabled.

## Folder Structure Changes

```text
enterprise-data-copilot/
  docker-compose.yml
  PROJECT_REQUIREMENTS.md
  docs/
    STEP_01_REDIS_ELASTICSEARCH.md
```

## Docker Desktop Requirement

Install Docker Desktop for your operating system:

- macOS: https://docs.docker.com/desktop/install/mac-install/
- Windows: https://docs.docker.com/desktop/install/windows-install/
- Linux: https://docs.docker.com/desktop/install/linux/

Recommended Docker Desktop resources for Elasticsearch:

- Memory: 4 GB minimum, 8 GB recommended
- CPU: 2 cores minimum
- Disk: at least 10 GB free

On Linux, Elasticsearch may require this host setting:

```bash
sudo sysctl -w vm.max_map_count=262144
```

## Images Used

- Redis: `redis:7.2-alpine`
- Elasticsearch: `docker.elastic.co/elasticsearch/elasticsearch:8.15.3`

## Pull Images

```bash
docker pull redis:7.2-alpine
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.15.3
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
enterprise-data-copilot-redis            healthy
enterprise-data-copilot-elasticsearch    healthy
```

Elasticsearch can take 30-90 seconds to become healthy.

## Verify Redis Connectivity

```bash
docker exec enterprise-data-copilot-redis redis-cli ping
```

Expected output:

```text
PONG
```

## Verify Elasticsearch Connectivity

```bash
curl http://localhost:9200
```

Expected output includes:

```json
{
  "cluster_name": "docker-cluster",
  "tagline": "You Know, for Search"
}
```

Check cluster health:

```bash
curl http://localhost:9200/_cluster/health?pretty
```

Expected output includes:

```json
{
  "status": "green"
}
```

For a single-node local cluster, `yellow` can also be acceptable during startup.

## Persistent Volumes

The compose file creates named Docker volumes:

```text
redis_data
elasticsearch_data
```

List them:

```bash
docker volume ls
```

Inspect them:

```bash
docker volume inspect enterprise-data-copilot_redis_data
docker volume inspect enterprise-data-copilot_elasticsearch_data
```

## Stop Infrastructure

```bash
docker compose down
```

## Stop And Delete Data

Use this only when you intentionally want a clean reset:

```bash
docker compose down -v
```

## Troubleshooting

If Elasticsearch exits immediately on Linux, run:

```bash
sudo sysctl -w vm.max_map_count=262144
docker compose up -d
```

If port `6379` or `9200` is already in use, stop the local service using that port or change the port mapping in `docker-compose.yml`.

If Docker Desktop is not running, start Docker Desktop first and then rerun:

```bash
docker compose up -d
```
