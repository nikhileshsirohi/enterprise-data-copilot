from fastapi import APIRouter, Depends, HTTPException

from backend.ai_service.services.workflow_state_store import RedisWorkflowStateStore

router = APIRouter()


def get_workflow_state_store() -> RedisWorkflowStateStore:
    return RedisWorkflowStateStore()


WorkflowStateStoreDependency = Depends(get_workflow_state_store)


@router.get("/{workflow_run_id}")
def get_workflow_run(
    workflow_run_id: str,
    state_store: RedisWorkflowStateStore = WorkflowStateStoreDependency,
) -> dict:
    payload = state_store.get_run(workflow_run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Workflow run was not found or expired.")
    return payload
