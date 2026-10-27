import React from "react";
import { UserPlus } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { NotConnectedState } from "@/design-system/components/NotConnectedState";

export const AdminView: React.FC = () => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Administration & Governance"
        breadcrumbs={[{ label: "System" }, { label: "Tenant Administration" }]}
        badges={<StatusPill label="ADMIN RBAC: ACTIVE" variant="info" />}
        actions={
          <Button variant="primary" size="sm" icon={<UserPlus className="w-3.5 h-3.5" />} disabled>
            Provision Tenant User
          </Button>
        }
      />

      <div className="flex-1 p-6 overflow-y-auto">
        <NotConnectedState
          moduleName="Tenant & System Administration"
          description="Tenant isolation settings, SCIM 2.0 user synchronizations, role assignments, and cryptographic key rotations will be managed here once the administrative API endpoints are connected."
          expectedEndpoint="GET /api/v1/admin/tenants"
        />
      </div>
    </div>
  );
};
