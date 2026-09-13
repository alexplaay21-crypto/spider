from api.backend_client import backend_client
from storage.local_state import LocalState


async def has_access(state: LocalState, module_id: str) -> tuple[bool, str]:
    """
    Section 30: modules never decide their own access, and Core never
    trusts a locally cached "plan" for this - it always asks Backend,
    live, every time (section 56/89 - Backend is the only source of
    truth).
    """
    result = await backend_client.check_license(state.account_id, module_id)
    return result["allowed"], result["reason"]
