from fastapi import APIRouter, Depends, HTTPException, status

from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user
from backend.ai_service.services.workflow_state_store import RedisWorkflowStateStore

router = APIRouter()


def get_workflow_state_store() -> RedisWorkflowStateStore:
    return RedisWorkflowStateStore()


WorkflowStateStoreDependency = Depends(get_workflow_state_store)
CurrentUserDependency = Depends(require_authenticated_user)


@router.get("/{workflow_run_id}")
def get_workflow_run(
    workflow_run_id: str,
    state_store: RedisWorkflowStateStore = WorkflowStateStoreDependency,
    current_user: AuthenticatedUser = CurrentUserDependency,
) -> dict:
    payload = state_store.get_run(workflow_run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Workflow run was not found or expired.")
    owner_user_id = payload.get("user_id")
    user_can_view = (
        owner_user_id == current_user.user_id
        or current_user.is_staff
    )
    if not user_can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workflow run.",
        )
    return payload
