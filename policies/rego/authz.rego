package elixir.authz

import future.keywords

default allow := false

# Allow Global Admin unconditionally
allow if {
    "GlobalAdmin" in input.user.roles
}

# Allow users with appropriate clearance
allow if {
    input.action == "content:read"
    input.user.tenant_id == input.resource.tenant_id
    input.resource.classification != "RESTRICTED"
}

# Allow Records Manager on records routes
allow if {
    "RecordsManager" in input.user.roles
    input.action in ["records:declare", "records:hold:apply", "records:hold:lift"]
    input.user.tenant_id == input.resource.tenant_id
}
