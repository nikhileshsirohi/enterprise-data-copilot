import json

from backend.ai_service.services.workflow_state_store import (
    RedisWorkflowStateStore,
    WorkflowCheckpoint,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.ttls = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value
        self.ttls[key] = ex


def test_workflow_state_store_records_checkpoints_and_completion() -> None:
    redis = FakeRedis()
    store = RedisWorkflowStateStore(redis_client=redis)

    run_id = store.start_run(
        question="committed quantity of PO1001",
        limit=5,
        chat_context_count=0,
        user_id=7,
    )
    store.append_checkpoint(
        run_id,
        WorkflowCheckpoint(
            node="generate_sql",
            status="VALID",
            metadata={"sql": "SELECT 1"},
        ),
    )
    store.complete_run(run_id, status="SUCCESS", metadata={"row_count": 1})

    key = f"langgraph:ask:{run_id}"
    payload = json.loads(redis.values[key])

    assert redis.ttls[key] == 86400
    assert payload["run_id"] == run_id
    assert payload["user_id"] == 7
    assert payload["status"] == "SUCCESS"
    assert payload["question"] == "committed quantity of PO1001"
    assert payload["checkpoints"][0]["node"] == "generate_sql"
    assert payload["checkpoints"][0]["status"] == "VALID"
    assert payload["result"]["row_count"] == 1
