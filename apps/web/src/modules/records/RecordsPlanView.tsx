import React from "react";
import { Lock, Clock } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { StatusPill } from "@/design-system/components/StatusPill";
import { Button } from "@/design-system/components/Button";
import { NotConnectedState } from "@/design-system/components/NotConnectedState";

export const RecordsPlanView: React.FC = () => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Records & Retention Management"
        breadcrumbs={[{ label: "Governance" }, { label: "Records & Legal Holds" }]}
        badges={<StatusPill label="DoD 5015.02 / ISO 15489" variant="record" />}
        actions={
          <>
            <Button variant="danger" size="sm" icon={<Lock className="w-3.5 h-3.5" />} disabled>
              Create Legal Hold
            </Button>
            <Button variant="secondary" size="sm" icon={<Clock className="w-3.5 h-3.5" />} disabled>
              Disposition Queue
            </Button>
          </>
        }
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        <NotConnectedState
          moduleName="Records & Retention Management Engine"
          description="Retention schedules, litigation holds, custodian tracking, and defensible disposition queues will be loaded dynamically from the records API. Mock sample rows and fake counts have been removed."
          expectedEndpoint="GET /api/v1/records/holds"
        />
      </div>
    </div>
  );
};
