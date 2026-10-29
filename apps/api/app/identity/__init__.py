"""Identity Module Package."""

from apps.api.app.identity.session import session_manager
from apps.api.app.tenancy.middleware import register_session_resolver


async def _resolve_session_tenant(session_id: str):
    sess = await session_manager.get_session(session_id)
    return sess.tenant_id if sess else None


register_session_resolver(_resolve_session_tenant)
