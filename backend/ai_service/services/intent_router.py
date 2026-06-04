import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Protocol

from backend.ai_service.services.llm_provider import TextGenerationClient, get_llm_client_and_model
from backend.ai_service.services.ollama_client import OllamaClient
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    def embed(self, model: str, text: str) -> list[float]: ...


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class IntentExample:
    intent: str
    text: str


class IntentRouter:
    policy_keywords = {
        "policy",
        "policies",
        "reimbursement",
        "expense",
        "travel",
        "remote work",
        "work remotely",
        "vpn",
        "mfa",
        "multi-factor",
        "data security",
        "confidential",
        "restricted data",
        "receipt",
        "receipts",
        "meal",
        "hotel",
        "approval",
        "least privilege",
    }
    database_patterns = (
        re.compile(r"\bPO\d+\b", re.IGNORECASE),
        re.compile(r"\bSO\d+\b", re.IGNORECASE),
        re.compile(r"\bMAT\d+\b", re.IGNORECASE),
        re.compile(r"\bCUST\d+\b", re.IGNORECASE),
        re.compile(r"\bSUP\d+\b", re.IGNORECASE),
    )
    database_keywords = {
        "supplier",
        "customer",
        "material",
        "stock",
        "inventory",
        "committed",
        "quantity",
        "purchase order",
        "sales order",
        "orders",
        "invoice",
        "shipment",
    }
    intent_examples = (
        IntentExample("policy", "What is the reimbursement limit for meals?"),
        IntentExample("policy", "Can employees work remotely three days per week?"),
        IntentExample("policy", "What does the data security policy say about VPN?"),
        IntentExample("policy", "Do receipts need to be submitted for travel expenses?"),
        IntentExample("database", "Available stock of material MAT0006"),
        IntentExample("database", "What is committed quantity of PO1001?"),
        IntentExample("database", "Who is supplier of PO1001?"),
        IntentExample("database", "Show top 5 customers by order quantity"),
    )

    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient | None = None,
        llm_client: TextGenerationClient | None = None,
    ) -> None:
        settings = get_settings()
        self.embedding_client = embedding_client or OllamaClient(settings.ollama_base_url)
        self.llm_client = llm_client

    def decide(self, question: str) -> IntentDecision:
        normalized = question.strip().lower()

        entity_decision = self._decide_by_entity(question)
        if entity_decision:
            return entity_decision

        keyword_decision = self._decide_by_keywords(normalized)
        if keyword_decision and keyword_decision.confidence >= 0.85:
            return keyword_decision

        embedding_decision = self._decide_by_embeddings(question)
        if embedding_decision:
            return embedding_decision

        if get_settings().intent_llm_fallback_enabled:
            llm_decision = self._decide_by_llm(question)
            if llm_decision:
                return llm_decision

        if keyword_decision:
            return keyword_decision

        return IntentDecision(
            intent="database",
            confidence=0.55,
            reason="Defaulted to live database because no clear policy intent was detected.",
        )

    def _decide_by_entity(self, question: str) -> IntentDecision | None:
        if any(pattern.search(question) for pattern in self.database_patterns):
            return IntentDecision(
                intent="database",
                confidence=0.95,
                reason="Stage 1 entity rule detected business entity code.",
            )
        return None

    def _decide_by_keywords(self, normalized: str) -> IntentDecision | None:
        policy_hits = [keyword for keyword in self.policy_keywords if keyword in normalized]
        database_hits = [keyword for keyword in self.database_keywords if keyword in normalized]

        if policy_hits and not database_hits:
            return IntentDecision(
                intent="policy",
                confidence=0.90,
                reason=(
                    "Stage 2 keyword rule detected policy terms: "
                    f"{', '.join(sorted(policy_hits))}."
                ),
            )
        if database_hits and not policy_hits:
            return IntentDecision(
                intent="database",
                confidence=0.82,
                reason=(
                    "Stage 2 keyword rule detected database terms: "
                    f"{', '.join(sorted(database_hits))}."
                ),
            )
        if policy_hits and database_hits:
            return IntentDecision(
                intent="policy" if len(policy_hits) > len(database_hits) else "database",
                confidence=0.65,
                reason=(
                    "Stage 2 keyword rule found mixed signals: "
                    f"policy={', '.join(sorted(policy_hits))}; "
                    f"database={', '.join(sorted(database_hits))}."
                ),
            )
        return None

    def _decide_by_embeddings(self, question: str) -> IntentDecision | None:
        settings = get_settings()
        try:
            question_embedding = self.embedding_client.embed(
                model=settings.ollama_embedding_model,
                text=question,
            )
            scored_examples = [
                (
                    example.intent,
                    example.text,
                    self._cosine_similarity(
                        question_embedding,
                        self.embedding_client.embed(
                            model=settings.ollama_embedding_model,
                            text=example.text,
                        ),
                    ),
                )
                for example in self.intent_examples
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("intent_router.embedding_failed error=%s", exc)
            return None

        best_intent, best_example, best_score = max(scored_examples, key=lambda item: item[2])
        if best_score >= settings.intent_embedding_confidence_threshold:
            return IntentDecision(
                intent=best_intent,
                confidence=round(float(best_score), 4),
                reason=(
                    "Stage 3 embedding similarity matched "
                    f"{best_intent} example {best_example!r}."
                ),
            )
        return None

    def _decide_by_llm(self, question: str) -> IntentDecision | None:
        llm_client, model = get_llm_client_and_model(
            task="reasoning",
            client_override=self.llm_client,
        )
        prompt = f"""
Classify this user question for an enterprise data copilot.

Allowed intents:
- policy: questions about HR/company policy PDFs, travel, reimbursement, remote work,
  security policy
- database: questions about live business data in PostgreSQL such as orders, suppliers,
  customers, inventory, materials

Return only compact JSON:
{{"intent":"policy|database","confidence":0.0,"reason":"short reason"}}

Question:
{question}
""".strip()
        try:
            payload = json.loads(llm_client.generate(model=model, prompt=prompt))
        except Exception as exc:  # noqa: BLE001
            logger.warning("intent_router.llm_failed error=%s", exc)
            return None

        intent = str(payload.get("intent", "")).lower().strip()
        if intent not in {"policy", "database"}:
            return None
        try:
            confidence = float(payload.get("confidence", 0.6))
        except (TypeError, ValueError):
            confidence = 0.6
        return IntentDecision(
            intent=intent,
            confidence=max(0.0, min(confidence, 1.0)),
            reason=f"Stage 4 LLM fallback: {payload.get('reason', 'classified by LLM')}",
        )

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return -1.0

        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return -1.0
        return dot / (left_norm * right_norm)
