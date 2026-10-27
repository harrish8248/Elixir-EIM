import React from "react";
import { Play } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { NotConnectedState } from "@/design-system/components/NotConnectedState";

export const WorkflowView: React.FC = () => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Process Automation & Workflows"
        breadcrumbs={[{ label: "Automation" }, { label: "Workflows" }]}
        badges={<StatusPill label="ENGINE: PENDING WIRING" variant="neutral" />}
        actions={
          <Button variant="primary" size="sm" icon={<Play className="w-3.5 h-3.5" />} disabled>
            Start New Process
          </Button>
        }
      />

      <div className="flex-1 p-6 overflow-y-auto">
        <NotConnectedState
          moduleName="Process Automation Engine"
          description="Business process execution models, human task queues, and automated record declaration triggers will be displayed here once connected to the workflow engine."
          expectedEndpoint="GET /api/v1/workflow/tasks"
        />
      </div>
    </div>
  );
};
