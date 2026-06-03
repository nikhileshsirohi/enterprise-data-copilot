import json
import logging
from dataclasses import dataclass
from time import time
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from backend.shared.config import get_settings
from backend.shared.redis_client import get_redis_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowCheckpoint:
    node: str
    status: str
    metadata: dict


class RedisWorkflowStateStore:
    def __init__(self, redis_client: Redis | None = None) -> None:
        self.redis_client = redis_client or get_redis_client()

    def start_run(
        self,
        *,
        question: str,
        limit: int | None,
        chat_context_count: int,
        user_id: int | None = None,
    ) -> str:
        run_id = uuid4().hex
        payload = {
            "run_id": run_id,
            "user_id": user_id,
            "status": "RUNNING",
            "question": question,
            "limit": limit,
            "chat_context_count": chat_context_count,
            "started_at": int(time()),
            "updated_at": int(time()),
            "checkpoints": [],
        }
        self._save(run_id, payload)
        logger.info("workflow_state.started run_id=%s", run_id)
        return run_id

    def append_checkpoint(self, run_id: str, checkpoint: WorkflowCheckpoint) -> None:
        payload = self._load(run_id)
        if not payload:
            return

        payload["checkpoints"].append(
            {
                "node": checkpoint.node,
                "status": checkpoint.status,
                "metadata": checkpoint.metadata,
                "created_at": int(time()),
            }
        )
        payload["updated_at"] = int(time())
        self._save(run_id, payload)
        logger.info(
            "workflow_state.checkpoint run_id=%s node=%s status=%s",
            run_id,
            checkpoint.node,
            checkpoint.status,
        )

    def complete_run(self, run_id: str, *, status: str, metadata: dict | None = None) -> None:
        payload = self._load(run_id)
        if not payload:
            return

        payload["status"] = status
        payload["completed_at"] = int(time())
        payload["updated_at"] = int(time())
        payload["result"] = metadata or {}
        self._save(run_id, payload)
        logger.info("workflow_state.completed run_id=%s status=%s", run_id, status)

    def get_run(self, run_id: str) -> dict | None:
        payload = self._load(run_id)
        if not payload:
            logger.info("workflow_state.not_found run_id=%s", run_id)
            return None
        logger.info("workflow_state.loaded run_id=%s status=%s", run_id, payload.get("status"))
        return payload

    def _key(self, run_id: str) -> str:
        settings = get_settings()
        return f"{settings.redis_langgraph_state_prefix}:{run_id}"

    def _load(self, run_id: str) -> dict | None:
        try:
            raw_payload = self.redis_client.get(self._key(run_id))
            if not raw_payload:
                return None
            return json.loads(raw_payload)
        except (RedisError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("workflow_state.load_failed run_id=%s error=%s", run_id, exc)
            return None

    def _save(self, run_id: str, payload: dict) -> None:
        settings = get_settings()
        try:
            self.redis_client.set(
                self._key(run_id),
                json.dumps(payload, default=str),
                ex=settings.langgraph_state_ttl_seconds,
            )
        except RedisError as exc:
            logger.warning("workflow_state.save_failed run_id=%s error=%s", run_id, exc)
