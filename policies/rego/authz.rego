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

# Governance roles check
has_governance_role if {
    some r in ["GlobalAdmin", "TenantAdmin", "RecordsManager", "ComplianceOfficer", "Auditor"]
    r in input.user.roles
}

# Sensitive actions check
is_dual_control_action if {
    input.action in [
        "records:hold:lift",
        "records:disposition:execute",
        "content:permanent_delete"
    ]
}

# Chained decision policy with unambiguous evaluation priority
decision := {
    "result": "allow",
    "reason": "Global platform administrator override",
    "obligations": ["audit_log", "notify_security"]
} if {
    "GlobalAdmin" in input.user.roles
} else := {
    "result": "deny",
    "reason": "Cross-tenant access violation: tenant mismatch between actor and resource",
    "obligations": ["audit_log", "raise_security_alert"]
} if {
    input.resource.tenant_id != ""
    input.user.tenant_id != input.resource.tenant_id
} else := {
    "result": "deny",
    "reason": sprintf("Insufficient security clearance: user clearance (%v) < resource classification (%v)", [
        input.user.clearance_level,
        classification_levels[input.resource.classification]
    ]),
    "obligations": ["audit_log"]
} if {
    classification_levels[input.resource.classification] > input.user.clearance_level
} else := {
    "result": "deny",
    "reason": sprintf("Department isolation: user department '%v' does not match resource department '%v'", [
        input.user.department,
        input.resource.department
    ]),
    "obligations": ["audit_log"]
} if {
    not has_governance_role
    input.resource.department != ""
    input.user.department != input.resource.department
} else := {
    "result": "require_approval",
    "reason": "Sensitive governance operation requires secondary officer approval and step-up MFA",
    "obligations": ["audit_log", "step_up_mfa", "dual_authorization"]
} if {
    is_dual_control_action
    "RecordsManager" in input.user.roles
    not input.context.has_approval
} else := {
    "result": "allow",
    "reason": "Sensitive governance operation approved with dual authorization",
    "obligations": ["audit_log", "retain_chain_proof"]
} if {
    is_dual_control_action
    "RecordsManager" in input.user.roles
    input.context.has_approval == true
} else := {
    "result": "allow",
    "reason": "Tenant administrator access within tenant boundary",
    "obligations": ["audit_log"]
} if {
    "TenantAdmin" in input.user.roles
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
        "audit:verify_chain",
        "content:read",
        "content:write"
    ]
} else := {
    "result": "allow",
    "reason": "Records management operations permitted within tenant",
    "obligations": ["audit_log"]
} if {
    some role in ["RecordsManager", "ComplianceOfficer"]
    role in input.user.roles
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
        "audit:read",
        "audit:verify_chain"
    ]
} else := {
    "result": "allow",
    "reason": "Auditor read-only inspection permitted",
    "obligations": ["audit_log"]
} if {
    "Auditor" in input.user.roles
    classification_levels[input.resource.classification] <= input.user.clearance_level
    input.action in [
        "audit:read",
        "audit:verify_chain",
        "records:schedule:read",
        "reports:read",
        "content:read"
    ]
} else := {
    "result": "allow",
    "reason": "Knowledge worker operational content access permitted",
    "obligations": ["audit_log"]
} if {
    "KnowledgeWorker" in input.user.roles
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
