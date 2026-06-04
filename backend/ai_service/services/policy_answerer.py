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
        search_limit = min(limit or 5, 10)
        results = self.policy_searcher.search(query=question, limit=search_limit)
        if not results:
            return AskResponse(
                question=question,
                answer="I could not find relevant company policy information for this question.",
                answer_source="policy",
                sql=None,
                is_sql_valid=True,
                validation_reason=None,
                columns=[],
                rows=[],
                row_count=0,
                truncated=False,
                metadata=[],
                policy_sources=[],
            )

        answer = self._summarize(question=question, results=results)
        return AskResponse(
            question=question,
            answer=answer,
            answer_source="policy",
            sql=None,
            is_sql_valid=True,
            validation_reason=None,
            columns=[],
            rows=[],
            row_count=len(results),
            truncated=False,
            metadata=[],
            policy_sources=[result.model_dump() for result in results],
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
Keep the answer concise and business friendly.

Policy context JSON:
{json.dumps(payload, indent=2)}

Answer:
""".strip()
