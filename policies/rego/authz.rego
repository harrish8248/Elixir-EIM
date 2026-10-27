package elixir.authz

import future.keywords

default decision := {
    "result": "deny",
    "reason": "Default deny: no matching authorization policy rule",
    "obligations": ["audit_log"]
}

# Classification to numeric clearance mapping
classification_levels := {
    "PUBLIC": 1,
    "INTERNAL": 2,
    "CONFIDENTIAL": 3,
    "RESTRICTED": 4,
    "TOP_SECRET": 5
}

# Shorthand for backward compatibility and simple PEP queries
default allow := false
allow if {
    decision.result == "allow"
}

# -----------------------------------------------------------------------------
# 1. Global Admin (Platform Administrator)
# -----------------------------------------------------------------------------
# Platform admin has full system-level access
decision := {
    "result": "allow",
    "reason": "Global platform administrator override",
    "obligations": ["audit_log", "notify_security"]
} if {
    "GlobalAdmin" in input.user.roles
}

# -----------------------------------------------------------------------------
# 2. Cross-Tenant Denial (Multi-Tenant Isolation)
# -----------------------------------------------------------------------------
# If not GlobalAdmin, tenant mismatch strictly denies
decision := {
    "result": "deny",
    "reason": "Cross-tenant access violation: tenant mismatch between actor and resource",
    "obligations": ["audit_log", "raise_security_alert"]
} if {
    not "GlobalAdmin" in input.user.roles
    input.resource.tenant_id != ""
    input.user.tenant_id != input.resource.tenant_id
}

# -----------------------------------------------------------------------------
# 3. Security Clearance & Classification (ABAC)
# -----------------------------------------------------------------------------
# Deny if resource classification exceeds user's clearance level
decision := {
    "result": "deny",
    "reason": sprintf("Insufficient security clearance: user clearance (%v) < resource classification (%v)", [
        input.user.clearance_level,
        classification_levels[input.resource.classification]
    ]),
    "obligations": ["audit_log"]
} if {
    not "GlobalAdmin" in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    classification_levels[input.resource.classification] > input.user.clearance_level
}

# -----------------------------------------------------------------------------
# 4. Department Isolation (ABAC)
# -----------------------------------------------------------------------------
# Deny if resource has a specific department and user is from a different department,
# unless user holds an administrative or governance role.
has_governance_role if {
    some r in ["GlobalAdmin", "TenantAdmin", "RecordsManager", "ComplianceOfficer", "Auditor"]
    r in input.user.roles
}

decision := {
    "result": "deny",
    "reason": sprintf("Department isolation: user department '%v' does not match resource department '%v'", [
        input.user.department,
        input.resource.department
    ]),
    "obligations": ["audit_log"]
} if {
    not has_governance_role
    input.user.tenant_id == input.resource.tenant_id
    input.resource.department != ""
    input.user.department != input.resource.department
}

# -----------------------------------------------------------------------------
# 5. Require Approval (Sensitive Governance Operations)
# -----------------------------------------------------------------------------
# Sensitive actions like lifting legal holds or permanent disposition require dual approval
is_dual_control_action if {
    input.action in [
        "records:hold:lift",
        "records:disposition:execute",
        "content:permanent_delete"
    ]
}

decision := {
    "result": "require_approval",
    "reason": "Sensitive governance operation requires secondary officer approval and step-up MFA",
    "obligations": ["audit_log", "step_up_mfa", "dual_authorization"]
} if {
    not "GlobalAdmin" in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    is_dual_control_action
    "RecordsManager" in input.user.roles
    not input.context.has_approval
}

decision := {
    "result": "allow",
    "reason": "Sensitive governance operation approved with dual authorization",
    "obligations": ["audit_log", "retain_chain_proof"]
} if {
    not "GlobalAdmin" in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    is_dual_control_action
    "RecordsManager" in input.user.roles
    input.context.has_approval == true
}

# -----------------------------------------------------------------------------
# 6. Tenant Admin Permissions
# -----------------------------------------------------------------------------
decision := {
    "result": "allow",
    "reason": "Tenant administrator access within tenant boundary",
    "obligations": ["audit_log"]
} if {
    "TenantAdmin" in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    not is_dual_control_action
    input.action in [
        "tenant:read",
        "tenant:write",
        "users:read",
        "users:manage",
        "groups:manage",
        "policies:manage",
        "scim:manage",
        "audit:read",
        "content:read",
        "content:write"
    ]
}

# -----------------------------------------------------------------------------
# 7. Records Manager / Compliance Officer Permissions
# -----------------------------------------------------------------------------
decision := {
    "result": "allow",
    "reason": "Records management operations permitted within tenant",
    "obligations": ["audit_log"]
} if {
    some role in ["RecordsManager", "ComplianceOfficer"]
    role in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    classification_levels[input.resource.classification] <= input.user.clearance_level
    not is_dual_control_action
    input.action in [
        "records:schedule:create",
        "records:schedule:read",
        "records:declare",
        "records:hold:apply",
        "records:disposition:review",
        "content:read",
        "content:write",
        "audit:read"
    ]
}

# -----------------------------------------------------------------------------
# 8. Knowledge Worker (Employee) Permissions
# -----------------------------------------------------------------------------
decision := {
    "result": "allow",
    "reason": "Knowledge worker operational content access permitted",
    "obligations": ["audit_log"]
} if {
    "KnowledgeWorker" in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    classification_levels[input.resource.classification] <= input.user.clearance_level
    input.user.department == input.resource.department
    input.action in [
        "content:create",
        "content:read",
        "content:write",
        "content:search",
        "workflow:submit",
        "workflow:task:view",
        "workflow:task:complete"
    ]
}

# -----------------------------------------------------------------------------
# 9. Auditor (Read-Only Compliance & Hash Verification)
# -----------------------------------------------------------------------------
decision := {
    "result": "allow",
    "reason": "Auditor read-only inspection permitted",
    "obligations": ["audit_log"]
} if {
    "Auditor" in input.user.roles
    input.user.tenant_id == input.resource.tenant_id
    classification_levels[input.resource.classification] <= input.user.clearance_level
    input.action in [
        "audit:read",
        "audit:verify_chain",
        "records:schedule:read",
        "reports:read",
        "content:read"
    ]
}
