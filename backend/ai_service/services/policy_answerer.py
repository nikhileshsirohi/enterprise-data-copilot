import json
import logging

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.schemas.policies import PolicySearchResult
from backend.ai_service.services.llm_provider import TextGenerationClient, get_llm_client_and_model
from backend.ai_service.services.policy_documents import PolicyVectorSearcher, build_policy_searcher
from backend.shared.config import get_settings

logger = logging.getLogger(__name__)


class PolicyAnswerer:
    def __init__(
        self,
        *,
        policy_searcher: PolicyVectorSearcher | None = None,
        llm_client: TextGenerationClient | None = None,
    ) -> None:
        self.policy_searcher = policy_searcher or build_policy_searcher()
        self.llm_client = llm_client

    def ask(self, question: str, limit: int | None = None) -> AskResponse:
        settings = get_settings()
        search_limit = min(limit or 5, 10)
        results = self.policy_searcher.search(query=question, limit=search_limit)
        filtered_results = [
            result for result in results if result.score >= settings.policy_rag_min_score
        ]
        if not filtered_results:
            return AskResponse(
                question=question,
                answer=(
                    "I could not find company policy information with enough confidence "
                    "to answer this question."
                ),
                answer_source="policy",
                sql=None,
                is_sql_valid=True,
                validation_reason=None,
                columns=[],
                rows=[],
                row_count=0,
                truncated=False,
                metadata=[
                    {
                        "policy_rag_min_score": settings.policy_rag_min_score,
                        "retrieved_policy_chunks": len(results),
                        "accepted_policy_chunks": 0,
                    }
                ],
                policy_sources=[],
                citations=[],
            )

        answer = self._summarize(question=question, results=filtered_results)
        return AskResponse(
            question=question,
            answer=answer,
            answer_source="policy",
            sql=None,
            is_sql_valid=True,
            validation_reason=None,
            columns=[],
            rows=[],
            row_count=len(filtered_results),
            truncated=False,
            metadata=[
                {
                    "policy_rag_min_score": settings.policy_rag_min_score,
                    "retrieved_policy_chunks": len(results),
                    "accepted_policy_chunks": len(filtered_results),
                }
            ],
            policy_sources=[result.model_dump() for result in filtered_results],
            citations=self._build_citations(filtered_results),
        )

    def _summarize(self, question: str, results: list[PolicySearchResult]) -> str:
        llm_client, model = get_llm_client_and_model(
            task="reasoning",
            client_override=self.llm_client,
        )
        prompt = self._build_prompt(question=question, results=results)
        settings = get_settings()
        logger.info(
            "policy_answer.llm_request provider=%s model=%s prompt_chars=%s chunks=%s",
            settings.llm_provider,
            model,
            len(prompt),
            len(results),
        )
        raw_answer = llm_client.generate(model=model, prompt=prompt).strip()
        logger.info("policy_answer.llm_response raw_answer=%r", raw_answer)
        return raw_answer

    def _build_prompt(self, question: str, results: list[PolicySearchResult]) -> str:
        payload = {
            "question": question,
            "policy_chunks": [
                {
                    "document_title": result.document_title,
                    "source_path": result.source_path,
                    "chunk_id": result.chunk_id,
                    "text": result.text,
                    "score": result.score,
                }
                for result in results
            ],
        }
        return f"""
You are an enterprise policy assistant.

Answer the user's question using only the provided policy chunks.
Do not use outside knowledge.
If the chunks do not contain the answer, say that the policy documents do not specify it.
Mention the policy document title in the answer.
Do not invent citations. The API will attach structured citations separately.
Keep the answer concise and business friendly.

Policy context JSON:
{json.dumps(payload, indent=2)}

Answer:
""".strip()

    def _build_citations(self, results: list[PolicySearchResult]) -> list[dict]:
        citations = []
        seen = set()
        for result in results:
            citation_key = (result.document_id, result.chunk_id)
            if citation_key in seen:
                continue
            seen.add(citation_key)
            citations.append(
                {
                    "source_type": "policy_document",
                    "document_id": result.document_id,
                    "document_title": result.document_title,
                    "source_path": result.source_path,
                    "chunk_id": result.chunk_id,
                    "chunk_index": result.chunk_index,
                    "score": round(result.score, 6),
                }
            )
        return citations
