"""Policy Decision Point (PDP) Client integrating with Open Policy Agent (OPA).

Enforces RBAC + ABAC decisions (allow, deny, require_approval).
Guarantees fail-closed semantics: any network failure, timeout, or OPA error results in strict denial.
"""

from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from apps.api.app.platform.config import settings
from apps.api.app.platform.logging import logger


class PdpDecision(BaseModel):
    """Normalized policy decision returned by the OPA Policy Decision Point."""

    result: str = Field(..., description="'allow', 'deny', or 'require_approval'")
    reason: str = Field(..., description="Human-readable policy rationale")
    obligations: list[str] = Field(default_factory=list, description="Downstream enforcement requirements")

    @property
    def is_allowed(self) -> bool:
        return self.result == "allow"

    @property
    def is_denied(self) -> bool:
        return self.result == "deny"

    @property
    def requires_approval(self) -> bool:
        return self.result == "require_approval"


class PdpClient:
    """Asynchronous client for evaluating authorization policies against OPA."""

    def __init__(self, opa_url: str | None = None, timeout_seconds: float = 2.0):
        # We query the decision endpoint
        base_url = (opa_url or settings.opa_url).rstrip("/")
        if not base_url.endswith("/decision"):
            self.endpoint = f"{base_url}/decision"
        else:
            self.endpoint = base_url
        self.timeout = timeout_seconds

    async def evaluate(
        self,
        *,
        user_id: UUID | str,
        tenant_id: UUID | str,
        roles: list[str],
        department: str | None = None,
        clearance_level: int = 1,
        action: str,
        resource_id: UUID | str = "",
        resource_tenant_id: UUID | str = "",
        resource_type: str = "document",
        resource_classification: str = "INTERNAL",
        resource_department: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PdpDecision:
        """
        Evaluate an authorization request against OPA.
        Fails closed: returns strict denial if OPA cannot be reached or errors.
        """
        payload = {
            "input": {
                "user": {
                    "id": str(user_id),
                    "tenant_id": str(tenant_id),
                    "roles": roles,
                    "department": department or "",
                    "clearance_level": clearance_level,
                },
                "resource": {
                    "id": str(resource_id),
                    "tenant_id": str(resource_tenant_id or tenant_id),
                    "type": resource_type,
                    "classification": resource_classification.upper(),
                    "department": resource_department or "",
                },
                "action": action,
                "context": context or {},
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.endpoint, json=payload)
                if res.status_code != 200:
                    logger.error(f"OPA returned non-200 status {res.status_code}: {res.text}")
                    return PdpDecision(
                        result="deny",
                        reason=f"Policy Decision Point error (status {res.status_code}) - fail closed",
                        obligations=["audit_log", "raise_pdp_alert"],
                    )

                body = res.json()
                raw_decision = body.get("result")
                if not raw_decision or not isinstance(raw_decision, dict):
                    logger.warning(f"OPA response missing structured decision: {body}")
                    return PdpDecision(
                        result="deny",
                        reason="Malformed PDP response: missing decision object - fail closed",
                        obligations=["audit_log"],
                    )

                return PdpDecision(
                    result=raw_decision.get("result", "deny"),
                    reason=raw_decision.get("reason", "Policy rule evaluation"),
                    obligations=raw_decision.get("obligations", ["audit_log"]),
                )

        except (httpx.TimeoutException, TimeoutError) as exc:
            logger.error(f"PDP evaluation timed out ({self.timeout}s): {exc}")
            return PdpDecision(
                result="deny",
                reason=f"Policy Decision Point timeout after {self.timeout}s - fail closed",
                obligations=["audit_log", "pdp_timeout_alert"],
            )
        except Exception as exc:
            logger.error(f"PDP connection error to {self.endpoint}: {exc}")
            return PdpDecision(
                result="deny",
                reason=f"Policy Decision Point unreachable ({type(exc).__name__}) - fail closed",
                obligations=["audit_log", "pdp_unavailable_alert"],
            )


# Global PDP client instance
pdp_client = PdpClient()
