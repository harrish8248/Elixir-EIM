import React, { useState, useEffect, useCallback } from "react";
import {
  Lock,
  Clock,
  ShieldAlert,
  FileCheck,
  Plus,
  RefreshCw,
  Unlock,
  CheckCircle,
  FileText,
} from "lucide-react";
import {
  apiClient,
  RetentionScheduleItem,
  LegalHoldItem,
  DocumentItem,
} from "@/api/client";
import { PageHeader } from "@/components/shell/PageHeader";
import { StatusPill } from "@/design-system/components/StatusPill";
import { Button } from "@/design-system/components/Button";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { Tabs } from "@/design-system/components/Tabs";
import { Modal } from "@/design-system/components/Modal";

export const RecordsPlanView: React.FC = () => {
  const [activeTab, setActiveTab] = useState("holds");
  const [schedules, setSchedules] = useState<RetentionScheduleItem[]>([]);
  const [holds, setHolds] = useState<LegalHoldItem[]>([]);
  const [dispositionQueue, setDispositionQueue] = useState<
    Array<{ document_id: string; name: string; retention_years: number; eligible_at: string; status: string }>
  >([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Modals
  const [isHoldModalOpen, setIsHoldModalOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [selectedHoldForRelease, setSelectedHoldForRelease] = useState<LegalHoldItem | null>(null);
  const [releaseReason, setReleaseReason] = useState("");
  const [notification, setNotification] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Form states: New Hold
  const [holdName, setHoldName] = useState("");
  const [holdMatter, setHoldMatter] = useState("");
  const [holdDesc, setHoldDesc] = useState("");
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  // Form states: New Schedule
  const [scheduleName, setScheduleName] = useState("");
  const [scheduleCode, setScheduleCode] = useState("");
  const [scheduleYears, setScheduleYears] = useState(7);
  const [scheduleDept, setScheduleDept] = useState("Finance");
  const [scheduleCls, setScheduleCls] = useState("CONFIDENTIAL");
  const [scheduleDesc, setScheduleDesc] = useState("");

  const showNotification = (message: string, type: "success" | "error" = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [schedulesRes, holdsRes, dispRes, docsRes] = await Promise.all([
        apiClient.listRetentionSchedules(),
        apiClient.listLegalHolds(),
        apiClient.getDispositionQueue(),
        apiClient.listDocuments(),
      ]);
      setSchedules(Array.isArray(schedulesRes) ? schedulesRes : (schedulesRes as any)?.items || []);
      setHolds(Array.isArray(holdsRes) ? holdsRes : (holdsRes as any)?.items || []);
      setDispositionQueue(Array.isArray(dispRes) ? dispRes : (dispRes as any)?.items || []);
      setDocuments(Array.isArray(docsRes) ? docsRes : (docsRes as any)?.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load records data";
      showNotification(msg, "error");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handlers
  const handleCreateHold = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!holdName.trim() || !holdMatter.trim()) return;

    try {
      await apiClient.createLegalHold({
        name: holdName.trim(),
        matter_number: holdMatter.trim(),
        description: holdDesc.trim(),
        document_ids: selectedDocIds,
      });
      setIsHoldModalOpen(false);
      setHoldName("");
      setHoldMatter("");
      setHoldDesc("");
      setSelectedDocIds([]);
      showNotification(`Litigation hold "${holdMatter}" enacted. Custodian documents locked.`);
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to place legal hold";
      showNotification(msg, "error");
    }
  };

  const handleReleaseHold = async () => {
    if (!selectedHoldForRelease) return;
    try {
      await apiClient.releaseLegalHold(selectedHoldForRelease.id, releaseReason);
      setSelectedHoldForRelease(null);
      setReleaseReason("");
      showNotification(`Legal hold "${selectedHoldForRelease.name}" released. Audit chain updated.`);
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to release hold";
      showNotification(msg, "error");
    }
  };

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scheduleName.trim() || !scheduleCode.trim()) return;

    try {
      await apiClient.createRetentionSchedule({
        name: scheduleName.trim(),
        schedule_code: scheduleCode.trim(),
        retention_years: Number(scheduleYears),
        department: scheduleDept,
        classification: scheduleCls,
        description: scheduleDesc.trim(),
      });
      setIsScheduleModalOpen(false);
      setScheduleName("");
      setScheduleCode("");
      setScheduleDesc("");
      showNotification(`Retention schedule "${scheduleCode}" registered.`);
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create schedule";
      showNotification(msg, "error");
    }
  };

  // Columns for Legal Holds
  const holdColumns: Column<LegalHoldItem>[] = [
    {
      id: "matter",
      header: "Matter #",
      width: "140px",
      accessor: (h) => <span className="font-mono text-xs font-bold text-surface-900">{h.matter_number || "—"}</span>,
    },
    {
      id: "name",
      header: "Hold Name & Scope",
      accessor: (h) => (
        <div>
          <span className="font-semibold text-surface-900 block">{h.name}</span>
          {h.description && <span className="text-[11px] text-surface-500 block">{h.description}</span>}
        </div>
      ),
    },
    {
      id: "status",
      header: "Status",
      width: "120px",
      accessor: (h) => (
        <StatusPill
          label={h.status === "ACTIVE" ? "ACTIVE HOLD" : "RELEASED"}
          variant={h.status === "ACTIVE" ? "hold" : "neutral"}
        />
      ),
    },
    {
      id: "targets",
      header: "Frozen Assets",
      width: "120px",
      accessor: (h) => (
        <span className="font-mono text-xs text-brand-800 font-semibold bg-brand-50 px-2 py-0.5 rounded border border-brand-200">
          {h.target_count} documents
        </span>
      ),
    },
    {
      id: "placed_by",
      header: "Custodian / Issuer",
      width: "160px",
      accessor: (h) => <span className="text-xs text-surface-600 truncate block">{h.placed_by_email}</span>,
    },
    {
      id: "created",
      header: "Date Placed",
      width: "110px",
      accessor: (h) => <span className="text-xs text-surface-500">{new Date(h.created_at).toLocaleDateString()}</span>,
    },
    {
      id: "actions",
      header: "Actions",
      width: "110px",
      accessor: (h) =>
        h.status === "ACTIVE" ? (
          <Button
            variant="outline"
            size="sm"
            icon={<Unlock className="w-3 h-3 text-red-600" />}
            onClick={(e) => {
              e.stopPropagation();
              setSelectedHoldForRelease(h);
            }}
          >
            Release
          </Button>
        ) : (
          <span className="text-[11px] text-surface-400 italic">Concluded</span>
        ),
    },
  ];

  // Columns for Retention Schedules
  const scheduleColumns: Column<RetentionScheduleItem>[] = [
    {
      id: "code",
      header: "Schedule Code",
      width: "140px",
      accessor: (s) => <span className="font-mono text-xs font-bold text-brand-900">{s.schedule_code || "—"}</span>,
    },
    {
      id: "name",
      header: "Schedule Name",
      accessor: (s) => (
        <div>
          <span className="font-semibold text-surface-900 block">{s.name}</span>
          {s.description && <span className="text-[11px] text-surface-500 block">{s.description}</span>}
        </div>
      ),
    },
    {
      id: "years",
      header: "Retention Period",
      width: "130px",
      accessor: (s) => (
        <span className="text-xs font-semibold text-surface-800 font-mono">
          {s.retention_years} {s.retention_years === 1 ? "Year" : "Years"}
        </span>
      ),
    },
    {
      id: "dept",
      header: "Department",
      width: "120px",
      accessor: (s) => <span className="text-xs text-surface-700">{s.department || "Enterprise Wide"}</span>,
    },
    {
      id: "cls",
      header: "Classification",
      width: "120px",
      accessor: (s) => (
        <StatusPill
          label={s.classification || "INTERNAL"}
          variant={s.classification === "CONFIDENTIAL" ? "warning" : "neutral"}
        />
      ),
    },
    {
      id: "status",
      header: "Status",
      width: "100px",
      accessor: (s) => (
        <StatusPill label={s.is_active ? "ENFORCED" : "INACTIVE"} variant={s.is_active ? "success" : "neutral"} />
      ),
    },
  ];

  const safeHolds = Array.isArray(holds) ? holds : [];
  const safeSchedules = Array.isArray(schedules) ? schedules : [];
  const safeDisposition = Array.isArray(dispositionQueue) ? dispositionQueue : [];

  // Tab definitions
  const tabItems = [
    {
      id: "holds",
      label: "Litigation & Legal Holds",
      badge: safeHolds.filter((h) => h.status === "ACTIVE").length,
      icon: <Lock className="w-3.5 h-3.5" />,
      content: (
        <div className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-surface-600">
              Legal holds override all automated retention and disposition rules. Preserved documents cannot be modified,
              trashed, or purged until explicitly released with audit rationale.
            </p>
            <Button
              variant="danger"
              size="sm"
              icon={<Lock className="w-3.5 h-3.5" />}
              onClick={() => setIsHoldModalOpen(true)}
            >
              Enact Legal Hold
            </Button>
          </div>
          <div className="bg-white rounded-lg border border-surface-200 shadow-xs overflow-hidden">
            <DataTable
              columns={holdColumns}
              data={safeHolds}
              keyExtractor={(h) => h.id}
              isLoading={isLoading}
              emptyMessage="No legal holds currently active."
            />
          </div>
        </div>
      ),
    },
    {
      id: "schedules",
      label: "Retention Schedules (DoD 5015.02)",
      badge: safeSchedules.length,
      icon: <FileCheck className="w-3.5 h-3.5" />,
      content: (
        <div className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-surface-600">
              Statutory retention rules configured to comply with SEC Rule 17a-4, FINRA, GDPR Art. 5, and HIPAA §164.
            </p>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => setIsScheduleModalOpen(true)}
            >
              New Retention Schedule
            </Button>
          </div>
          <div className="bg-white rounded-lg border border-surface-200 shadow-xs overflow-hidden">
            <DataTable
              columns={scheduleColumns}
              data={safeSchedules}
              keyExtractor={(s) => s.id}
              isLoading={isLoading}
              emptyMessage="No retention schedules configured."
            />
          </div>
        </div>
      ),
    },
    {
      id: "disposition",
      label: "Defensible Disposition Queue",
      badge: safeDisposition.length,
      icon: <Clock className="w-3.5 h-3.5" />,
      content: (
        <div className="p-4 space-y-4">
          <p className="text-xs text-surface-600">
            Records eligible for defensible destruction based on expired retention schedules. Every disposition requires
            Records Manager review and permanent cryptographic certificate generation.
          </p>
          <div className="bg-white rounded-lg border border-surface-200 shadow-xs p-6 text-center">
            {safeDisposition.length === 0 ? (
              <div className="space-y-2">
                <CheckCircle className="w-8 h-8 text-emerald-600 mx-auto" />
                <h4 className="text-xs font-bold text-surface-900">Zero Pending Dispositions</h4>
                <p className="text-xs text-surface-500 max-w-md mx-auto">
                  All active enterprise records remain within their statutory retention windows. No documents currently
                  qualify for certificate-of-destruction workflows.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {safeDisposition.map((item) => (
                  <div key={item.document_id} className="flex items-center justify-between p-3 border rounded text-xs">
                    <span className="font-semibold text-surface-900">{item.name}</span>
                    <span className="text-amber-700 font-mono">Eligible: {item.eligible_at}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`absolute top-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-semibold ${
            notification.type === "success" ? "bg-emerald-800 text-white" : "bg-red-800 text-white"
          }`}
        >
          {notification.type === "success" ? <CheckCircle className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
          {notification.message}
        </div>
      )}

      <PageHeader
        title="Records & Retention Management"
        breadcrumbs={[{ label: "Governance" }, { label: "Records & Legal Holds" }]}
        badges={<StatusPill label="DoD 5015.02 / ISO 15489 COMPLIANT" variant="record" />}
        actions={
          <Button
            variant="outline"
            size="sm"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
            onClick={loadData}
          >
            Refresh
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto">
        <Tabs items={tabItems} value={activeTab} onValueChange={setActiveTab} />
      </div>

      {/* Modal: Enact Legal Hold */}
      <Modal
        open={isHoldModalOpen}
        onOpenChange={setIsHoldModalOpen}
        title="Enact Litigation / Regulatory Legal Hold"
        description="Creates an immutable legal preservation hold. Target documents will be locked against deletion or modifications."
      >
        <form onSubmit={handleCreateHold} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Matter / Case Number</label>
              <input
                type="text"
                required
                value={holdMatter}
                onChange={(e) => setHoldMatter(e.target.value)}
                placeholder="e.g. DOJ-CIVIL-891"
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Hold Title</label>
              <input
                type="text"
                required
                value={holdName}
                onChange={(e) => setHoldName(e.target.value)}
                placeholder="e.g. DOJ Q3 Inquiry"
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Scope & Legal Description</label>
            <textarea
              rows={2}
              value={holdDesc}
              onChange={(e) => setHoldDesc(e.target.value)}
              placeholder="Preserve all financial ledgers, audit statements, and correspondence related to matter..."
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">
              Select Target Documents to Freeze ({selectedDocIds.length} selected)
            </label>
            <div className="max-h-36 overflow-y-auto border border-surface-200 rounded p-2 bg-surface-50 space-y-1">
              {documents.map((d) => (
                <label key={d.id} className="flex items-center gap-2 p-1.5 rounded hover:bg-white text-xs cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedDocIds.includes(d.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedDocIds([...selectedDocIds, d.id]);
                      } else {
                        setSelectedDocIds(selectedDocIds.filter((id) => id !== d.id));
                      }
                    }}
                    className="rounded text-brand-600"
                  />
                  <FileText className="w-3.5 h-3.5 text-surface-500" />
                  <span className="truncate font-medium text-surface-800">{d.name}</span>
                  <span className="text-[10px] text-surface-400 font-mono ml-auto">{d.classification}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsHoldModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="danger" size="sm" disabled={!holdName.trim() || !holdMatter.trim()}>
              Enact Legal Hold
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: New Retention Schedule */}
      <Modal
        open={isScheduleModalOpen}
        onOpenChange={setIsScheduleModalOpen}
        title="Register Retention Schedule"
        description="Defines a statutory record schedule under DoD 5015.02 compliance."
      >
        <form onSubmit={handleCreateSchedule} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Schedule Name</label>
              <input
                type="text"
                required
                value={scheduleName}
                onChange={(e) => setScheduleName(e.target.value)}
                placeholder="e.g. FINRA Books & Records"
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Code / Regulation</label>
              <input
                type="text"
                required
                value={scheduleCode}
                onChange={(e) => setScheduleCode(e.target.value)}
                placeholder="e.g. FINRA-RULE-4511"
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Retention (Years)</label>
              <input
                type="number"
                min={1}
                max={99}
                value={scheduleYears}
                onChange={(e) => setScheduleYears(Number(e.target.value))}
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Department</label>
              <input
                type="text"
                value={scheduleDept}
                onChange={(e) => setScheduleDept(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Classification</label>
              <select
                value={scheduleCls}
                onChange={(e) => setScheduleCls(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              >
                <option value="INTERNAL">INTERNAL</option>
                <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                <option value="RESTRICTED">RESTRICTED</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Regulatory Authority & Scope</label>
            <textarea
              rows={2}
              value={scheduleDesc}
              onChange={(e) => setScheduleDesc(e.target.value)}
              placeholder="Mandatory 6-year retention per FINRA Rule 4511 for all customer account records..."
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsScheduleModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={!scheduleName.trim() || !scheduleCode.trim()}>
              Register Schedule
            </Button>
          </div>
        </form>
      </Modal>

      {/* Release Hold Confirmation Modal */}
      <Modal
        open={selectedHoldForRelease !== null}
        onOpenChange={(open) => !open && setSelectedHoldForRelease(null)}
        title="Release Legal Hold"
        description={`Releasing "${selectedHoldForRelease?.name}" will unlock associated documents for normal retention processing.`}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Mandatory Release Reason</label>
            <textarea
              rows={3}
              required
              value={releaseReason}
              onChange={(e) => setReleaseReason(e.target.value)}
              placeholder="e.g. Investigation formally closed by legal counsel on 2026-10-27..."
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setSelectedHoldForRelease(null)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              disabled={!releaseReason.trim()}
              onClick={handleReleaseHold}
            >
              Confirm Hold Release
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default RecordsPlanView;
