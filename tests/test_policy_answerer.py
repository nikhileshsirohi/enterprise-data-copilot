from backend.ai_service.schemas.policies import PolicySearchResult
from backend.ai_service.services.policy_answerer import PolicyAnswerer


class FakePolicySearcher:
    def search(self, query: str, limit: int = 5):
        assert query == "What is the reimbursement limit for meals?"
        assert limit == 3
        return [
            PolicySearchResult(
                document_id="travel-expense-policy",
                document_title="Travel Expense Policy",
                source_path="data/company_policies/travel-expense-policy.pdf",
                chunk_id="travel-expense-policy:0",
                chunk_index=0,
                text="Meal reimbursement is capped at 60 USD per day.",
                score=0.91,
            )
        ]


class FakeLLMClient:
    def generate(self, model: str, prompt: str) -> str:
        assert model
        assert "Meal reimbursement is capped at 60 USD per day." in prompt
        assert "Travel Expense Policy" in prompt
        return (
            "Meal reimbursement is capped at 60 USD per day, "
            "according to the Travel Expense Policy."
        )


def test_policy_answerer_returns_rag_answer_with_sources() -> None:
    response = PolicyAnswerer(
        policy_searcher=FakePolicySearcher(),
        llm_client=FakeLLMClient(),
    ).ask("What is the reimbursement limit for meals?", limit=3)

    assert response.answer_source == "policy"
    assert response.sql is None
    assert response.row_count == 1
    assert response.metadata[0]["policy_rag_min_score"] == 0.75
    assert response.metadata[0]["accepted_policy_chunks"] == 1
    assert response.policy_sources[0]["document_id"] == "travel-expense-policy"
    assert "60 USD per day" in response.answer


def test_policy_answerer_handles_no_results() -> None:
    class EmptyPolicySearcher:
        def search(self, query: str, limit: int = 5):
            return []

    response = PolicyAnswerer(policy_searcher=EmptyPolicySearcher()).ask("unknown policy")

    assert response.answer_source == "policy"
    assert response.row_count == 0
    assert response.policy_sources == []
    assert "enough confidence" in response.answer.lower()


def test_policy_answerer_rejects_low_score_results() -> None:
    class LowScorePolicySearcher:
        def search(self, query: str, limit: int = 5):
            return [
                PolicySearchResult(
                    document_id="remote-work-policy",
                    document_title="Remote Work Policy",
                    source_path="data/company_policies/remote-work-policy.pdf",
                    chunk_id="remote-work-policy:0",
                    chunk_index=0,
                    text="Remote work requires manager approval.",
                    score=0.50,
                )
            ]

    response = PolicyAnswerer(policy_searcher=LowScorePolicySearcher()).ask(
        "What is the reimbursement limit for meals?"
    )

    assert response.row_count == 0
    assert response.policy_sources == []
    assert response.metadata[0]["retrieved_policy_chunks"] == 1
    assert response.metadata[0]["accepted_policy_chunks"] == 0
