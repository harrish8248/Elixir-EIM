import { ShieldAlert, Lock, CheckCircle2, Clock } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { StatusPill } from "@/design-system/components/StatusPill";
import { Button } from "@/design-system/components/Button";

interface LegalHoldItem {
  id: string;
  name: string;
  matterNumber: string;
  custodianCount: number;
  targetedDocuments: number;
  status: "ACTIVE" | "LIFTED";
  createdDate: string;
}

export const RecordsPlanView: React.FC = () => {
  const legalHolds: LegalHoldItem[] = [
    {
      id: "hold-01",
      name: "Matter 2026-0891: Antitrust Review & Contracts",
      matterNumber: "CASE-2026-0891",
      custodianCount: 14,
      targetedDocuments: 342,
      status: "ACTIVE",
      createdDate: "2026-09-12",
    },
    {
      id: "hold-02",
      name: "Matter 2026-0412: Patent Cross-Licensing Dispute",
      matterNumber: "CASE-2026-0412",
      custodianCount: 6,
      targetedDocuments: 89,
      status: "ACTIVE",
      createdDate: "2026-10-01",
    },
  ];

  const columns: Column<LegalHoldItem>[] = [
    {
      id: "matterNumber",
      header: "Matter #",
      width: "140px",
      accessor: (h) => <span className="font-mono text-xs text-brand-700 font-semibold">{h.matterNumber}</span>,
    },
    {
      id: "name",
      header: "Legal Hold Name",
      accessor: (h) => (
        <div className="flex items-center gap-2">
          <Lock className="w-3.5 h-3.5 text-status-danger shrink-0" />
          <span className="font-medium text-surface-900">{h.name}</span>
        </div>
      ),
    },
    {
      id: "custodians",
      header: "Custodians",
      width: "100px",
      accessor: (h) => <span className="text-surface-700">{h.custodianCount} users</span>,
    },
    {
      id: "targetedDocs",
      header: "Frozen Documents",
      width: "140px",
      accessor: (h) => (
        <span className="font-semibold text-status-danger">{h.targetedDocuments} items</span>
      ),
    },
    {
      id: "status",
      header: "Status",
      width: "110px",
      accessor: (h) => (
        <StatusPill label={h.status} variant={h.status === "ACTIVE" ? "hold" : "neutral"} />
      ),
    },
    {
      id: "createdDate",
      header: "Initiated",
      width: "110px",
      accessor: (h) => <span className="text-surface-500 text-xs font-mono">{h.createdDate}</span>,
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Records & Retention Management"
        breadcrumbs={[{ label: "Governance" }, { label: "Records & Legal Holds" }]}
        badges={<StatusPill label="DoD 5015.02 / ISO 15489" variant="record" />}
        actions={
          <>
            <Button variant="danger" size="sm" icon={<Lock className="w-3.5 h-3.5" />}>
              Create Legal Hold
            </Button>
            <Button variant="secondary" size="sm" icon={<Clock className="w-3.5 h-3.5" />}>
              Disposition Queue (18 Due)
            </Button>
          </>
        }
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* KPI Cards */}
        <div className="grid grid-cols-4 gap-4">
          <div className="p-4 bg-white border border-surface-200 rounded-lg shadow-sm">
            <span className="text-xs text-surface-500 font-medium">Declared Records</span>
            <div className="text-2xl font-bold text-surface-900 mt-1">48,912</div>
            <span className="text-[11px] text-emerald-600 flex items-center gap-1 mt-1 font-mono">
              <CheckCircle2 className="w-3 h-3" /> 100% Immutably Locked
            </span>
          </div>

          <div className="p-4 bg-white border border-surface-200 rounded-lg shadow-sm">
            <span className="text-xs text-surface-500 font-medium">Active Legal Holds</span>
            <div className="text-2xl font-bold text-status-danger mt-1">2 Holds</div>
            <span className="text-[11px] text-red-600 font-mono mt-1 block">
              431 Documents Frozen
            </span>
          </div>

          <div className="p-4 bg-white border border-surface-200 rounded-lg shadow-sm">
            <span className="text-xs text-surface-500 font-medium">Pending Disposition Review</span>
            <div className="text-2xl font-bold text-amber-600 mt-1">18 Items</div>
            <span className="text-[11px] text-surface-500 font-mono mt-1 block">
              Retention expired, review required
            </span>
          </div>

          <div className="p-4 bg-white border border-surface-200 rounded-lg shadow-sm">
            <span className="text-xs text-surface-500 font-medium">Defensibly Purged (YTD)</span>
            <div className="text-2xl font-bold text-surface-700 mt-1">3,204</div>
            <span className="text-[11px] text-surface-500 font-mono mt-1 block">
              Cryptographic certificates issued
            </span>
          </div>
        </div>

        {/* Legal Holds Table */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-surface-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-status-danger" /> Active Legal Litigation Holds
            </h2>
            <span className="text-xs text-surface-500">
              Documents linked to active holds cannot be updated or purged by any actor.
            </span>
          </div>

          <DataTable
            columns={columns}
            data={legalHolds}
            keyExtractor={(h) => h.id}
          />
        </div>
      </div>
    </div>
  );
};
