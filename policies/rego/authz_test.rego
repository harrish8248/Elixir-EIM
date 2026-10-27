package elixir.authz_test

import future.keywords
import data.elixir.authz

# 1. Global Admin
test_global_admin_allowed if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["GlobalAdmin"],
            "clearance_level": 5,
            "department": "IT"
        },
        "resource": {
            "tenant_id": "tenant-2",
            "classification": "TOP_SECRET",
            "department": "Finance"
        },
        "action": "system:configure",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "allow"
    "notify_security" in d.obligations
}

# 2. Cross-Tenant Denial
test_cross_tenant_denied if {
    input := {
        "user": {
            "tenant_id": "tenant-acrocorp",
            "roles": ["KnowledgeWorker"],
            "clearance_level": 3,
            "department": "Engineering"
        },
        "resource": {
            "tenant_id": "tenant-fincorp",
            "classification": "INTERNAL",
            "department": "Engineering"
        },
        "action": "content:read",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "deny"
    contains(d.reason, "Cross-tenant access violation")
}

# 3. Security Clearance (Insufficient)
test_insufficient_clearance_denied if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["KnowledgeWorker"],
            "clearance_level": 2, # INTERNAL clearance
            "department": "Engineering"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "RESTRICTED", # Clearance 4 required
            "department": "Engineering"
        },
        "action": "content:read",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "deny"
    contains(d.reason, "Insufficient security clearance")
}

# 4. Department Isolation
test_department_isolation_denied if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["KnowledgeWorker"],
            "clearance_level": 3,
            "department": "Marketing"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "INTERNAL",
            "department": "Finance"
        },
        "action": "content:read",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "deny"
    contains(d.reason, "Department isolation")
}

# 5. Dual Control / Require Approval
test_legal_hold_lift_requires_approval if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["RecordsManager"],
            "clearance_level": 3,
            "department": "Legal"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "CONFIDENTIAL",
            "department": "Legal"
        },
        "action": "records:hold:lift",
        "context": {"has_approval": false}
    }
    d := authz.decision with input as input
    d.result == "require_approval"
    "step_up_mfa" in d.obligations
    "dual_authorization" in d.obligations
}

test_legal_hold_lift_allowed_when_approved if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["RecordsManager"],
            "clearance_level": 3,
            "department": "Legal"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "CONFIDENTIAL",
            "department": "Legal"
        },
        "action": "records:hold:lift",
        "context": {"has_approval": true}
    }
    d := authz.decision with input as input
    d.result == "allow"
}

# 6. Tenant Admin Permissions
test_tenant_admin_allowed_tenant_routes if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["TenantAdmin"],
            "clearance_level": 4,
            "department": "Executive"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "INTERNAL",
            "department": "Finance"
        },
        "action": "users:manage",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "allow"
}

# 7. Knowledge Worker Allowed within Department & Clearance
test_knowledge_worker_content_read_allowed if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["KnowledgeWorker"],
            "clearance_level": 2,
            "department": "Engineering"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "INTERNAL",
            "department": "Engineering"
        },
        "action": "content:read",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "allow"
}

# 8. Auditor Read Allowed vs Auditor Write Denied
test_auditor_read_allowed if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["Auditor"],
            "clearance_level": 3,
            "department": "Audit"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "CONFIDENTIAL",
            "department": "Finance"
        },
        "action": "audit:verify_chain",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "allow"
}

test_auditor_write_denied if {
    input := {
        "user": {
            "tenant_id": "tenant-1",
            "roles": ["Auditor"],
            "clearance_level": 3,
            "department": "Audit"
        },
        "resource": {
            "tenant_id": "tenant-1",
            "classification": "CONFIDENTIAL",
            "department": "Finance"
        },
        "action": "content:write",
        "context": {}
    }
    d := authz.decision with input as input
    d.result == "deny"
}
