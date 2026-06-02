import json
import logging
import math
import re
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

BUSINESS_ALIAS_REPLACEMENTS = (
    (re.compile(r"\bqty\b", re.IGNORECASE), "quantity"),
    (re.compile(r"\bcommitted\s+qty\b", re.IGNORECASE), "committed quantity"),
    (re.compile(r"\bcommit\s+qty\b", re.IGNORECASE), "committed quantity"),
    (re.compile(r"\bpo\s*([0-9]+)\b", re.IGNORECASE), r"po \1"),
    (re.compile(r"\bso\s*([0-9]+)\b", re.IGNORECASE), r"so \1"),
    (re.compile(r"\bmat\s*([0-9]+)\b", re.IGNORECASE), r"mat \1"),
    (re.compile(r"\bcust\s*([0-9]+)\b", re.IGNORECASE), r"cust \1"),
    (re.compile(r"\bsup\s*([0-9]+)\b", re.IGNORECASE), r"sup \1"),
)

ENTITY_PATTERN = re.compile(r"\b(po|so|mat|cust|sup)\s*([0-9]+)\b", re.IGNORECASE)


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

        normalized_question = self._normalize_question(question)
        question_fingerprint = self._fingerprint(normalized_question)
        question_embedding = self._embed(normalized_question)
        best_key = None
        best_similarity = -1.0
        best_response = None
        best_business_match = False

        try:
            keys = list(self.redis_client.scan_iter(f"{settings.redis_semantic_cache_prefix}:*"))
            logger.info(
                "semantic_cache.lookup_start keys=%s threshold=%s business_threshold=%s",
                len(keys),
                settings.semantic_cache_threshold,
                settings.semantic_cache_business_threshold,
            )
            for key in keys:
                raw_payload = self.redis_client.get(key)
                if not raw_payload:
                    continue

                payload = json.loads(raw_payload)
                stored_fingerprint = payload.get("question_fingerprint")
                if stored_fingerprint is None:
                    stored_fingerprint = self._fingerprint(payload.get("question", ""))
                similarity = self._cosine_similarity(
                    question_embedding,
                    payload["question_embedding"],
                )
                if similarity > best_similarity:
                    best_key = key
                    best_similarity = similarity
                    best_response = payload["response"]
                    best_business_match = self._has_business_match(
                        question_fingerprint,
                        stored_fingerprint,
                    )
        except (RedisError, KeyError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("semantic_cache.lookup_failed error=%s", exc)
            return None

        strict_hit = best_similarity >= settings.semantic_cache_threshold
        business_hit = (
            best_business_match
            and best_similarity >= settings.semantic_cache_business_threshold
        )

        if best_key and best_response and (strict_hit or business_hit):
            logger.info(
                "semantic_cache.hit key=%s similarity=%s match_type=%s",
                best_key,
                best_similarity,
                "strict" if strict_hit else "business",
            )
            response = AskResponse(**best_response).model_copy(
                update={
                    "cache_hit": True,
                    "cache_similarity": best_similarity,
                    "cache_key": best_key,
                }
            )
            return SemanticCacheHit(key=best_key, similarity=best_similarity, response=response)

        logger.info(
            "semantic_cache.miss best_similarity=%s business_match=%s",
            best_similarity,
            best_business_match,
        )
        return None

    def set(self, question: str, response: AskResponse) -> str | None:
        settings = get_settings()
        if not settings.semantic_cache_enabled:
            return None
        if response.cache_hit or not response.is_sql_valid or response.execution_error:
            return None

        normalized_question = self._normalize_question(question)
        key = f"{settings.redis_semantic_cache_prefix}:{uuid4().hex}"
        payload = {
            "question": question,
            "normalized_question": normalized_question,
            "question_fingerprint": self._fingerprint(normalized_question),
            "question_embedding": self._embed(normalized_question),
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

    def _normalize_question(self, question: str) -> str:
        normalized = question.strip().lower()
        for pattern, replacement in BUSINESS_ALIAS_REPLACEMENTS:
            normalized = pattern.sub(replacement, normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _fingerprint(self, normalized_question: str) -> dict[str, list[str]]:
        entities = {
            f"{match.group(1).lower()}{match.group(2)}"
            for match in ENTITY_PATTERN.finditer(normalized_question)
        }
        intents = set()
        if "committed quantity" in normalized_question or "commit quantity" in normalized_question:
            intents.add("committed_quantity")
        if "supplier" in normalized_question:
            intents.add("supplier")
        if "stock" in normalized_question or "inventory" in normalized_question:
            intents.add("stock")
        if "order" in normalized_question:
            intents.add("order")

        return {
            "entities": sorted(entities),
            "intents": sorted(intents),
        }

    def _has_business_match(
        self,
        left: dict[str, list[str]],
        right: dict[str, list[str]],
    ) -> bool:
        left_entities = set(left.get("entities", []))
        right_entities = set(right.get("entities", []))
        left_intents = set(left.get("intents", []))
        right_intents = set(right.get("intents", []))

        return bool(left_entities & right_entities and left_intents & right_intents)
