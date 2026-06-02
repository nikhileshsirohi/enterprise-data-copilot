import json
import logging
import math
from dataclasses import dataclass
from time import time
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.services.ollama_client import OllamaClient
from backend.shared.config import get_settings
from backend.shared.redis_client import get_redis_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticCacheHit:
    key: str
    similarity: float
    response: AskResponse


class SemanticCache:
    def __init__(
        self,
        redis_client: Redis | None = None,
        embedding_client: OllamaClient | None = None,
    ) -> None:
        settings = get_settings()
        self.redis_client = redis_client or get_redis_client()
        self.embedding_client = embedding_client or OllamaClient(settings.ollama_base_url)

    def get(self, question: str) -> SemanticCacheHit | None:
        settings = get_settings()
        if not settings.semantic_cache_enabled:
            logger.info("semantic_cache.disabled")
            return None

        question_embedding = self._embed(question)
        best_key = None
        best_similarity = -1.0
        best_response = None

        try:
            keys = list(self.redis_client.scan_iter(f"{settings.redis_semantic_cache_prefix}:*"))
            logger.info(
                "semantic_cache.lookup_start keys=%s threshold=%s",
                len(keys),
                settings.semantic_cache_threshold,
            )
            for key in keys:
                raw_payload = self.redis_client.get(key)
                if not raw_payload:
                    continue

                payload = json.loads(raw_payload)
                similarity = self._cosine_similarity(
                    question_embedding,
                    payload["question_embedding"],
                )
                if similarity > best_similarity:
                    best_key = key
                    best_similarity = similarity
                    best_response = payload["response"]
        except (RedisError, KeyError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("semantic_cache.lookup_failed error=%s", exc)
            return None

        if best_key and best_response and best_similarity >= settings.semantic_cache_threshold:
            logger.info("semantic_cache.hit key=%s similarity=%s", best_key, best_similarity)
            response = AskResponse(**best_response).model_copy(
                update={
                    "cache_hit": True,
                    "cache_similarity": best_similarity,
                    "cache_key": best_key,
                }
            )
            return SemanticCacheHit(key=best_key, similarity=best_similarity, response=response)

        logger.info("semantic_cache.miss best_similarity=%s", best_similarity)
        return None

    def set(self, question: str, response: AskResponse) -> str | None:
        settings = get_settings()
        if not settings.semantic_cache_enabled:
            return None
        if response.cache_hit or not response.is_sql_valid or response.execution_error:
            return None

        key = f"{settings.redis_semantic_cache_prefix}:{uuid4().hex}"
        payload = {
            "question": question,
            "question_embedding": self._embed(question),
            "generated_sql": response.sql,
            "final_answer": response.answer,
            "timestamp": int(time()),
            "response": response.model_copy(
                update={
                    "cache_hit": False,
                    "cache_similarity": None,
                    "cache_key": key,
                }
            ).model_dump(),
        }

        try:
            self.redis_client.set(
                key,
                json.dumps(payload),
                ex=settings.semantic_cache_ttl_seconds,
            )
            logger.info(
                "semantic_cache.stored key=%s ttl=%s",
                key,
                settings.semantic_cache_ttl_seconds,
            )
            return key
        except RedisError as exc:
            logger.warning("semantic_cache.store_failed error=%s", exc)
            return None

    def _embed(self, text: str) -> list[float]:
        settings = get_settings()
        logger.info(
            "semantic_cache.embedding_request model=%s text=%r",
            settings.ollama_embedding_model,
            text,
        )
        embedding = self.embedding_client.embed(model=settings.ollama_embedding_model, text=text)
        logger.info("semantic_cache.embedding_response dimensions=%s", len(embedding))
        return embedding

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return -1.0

        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return -1.0

        return dot / (left_norm * right_norm)
