from backend.ai_service.services.intent_router import IntentRouter


def test_intent_router_routes_policy_questions_to_policy_rag() -> None:
    decision = IntentRouter().decide("What is the reimbursement limit for meals?")

    assert decision.intent == "policy"
    assert decision.confidence == 0.90
    assert "reimbursement" in decision.reason


def test_intent_router_routes_business_entity_questions_to_database() -> None:
    decision = IntentRouter().decide("Available stock of material MAT0006")

    assert decision.intent == "database"
    assert decision.confidence == 0.95
    assert "business entity code" in decision.reason


def test_intent_router_defaults_unclear_questions_to_database() -> None:
    decision = IntentRouter().decide("show recent activity")

    assert decision.intent == "database"
    assert decision.confidence == 0.55
