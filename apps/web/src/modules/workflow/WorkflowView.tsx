import React, { useState, useEffect, useCallback } from "react";
import {
  CheckCircle,
  XCircle,
  FileText,
  RefreshCw,
  Plus,
  ShieldAlert,
} from "lucide-react";
import {
  apiClient,
  WorkflowTaskItem,
  DocumentItem,
} from "@/api/client";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { Modal } from "@/design-system/components/Modal";

export const WorkflowView: React.FC = () => {
  const [tasks, setTasks] = useState<WorkflowTaskItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [isLoading, setIsLoading] = useState(false);

  // Modals
  const [isNewTaskModalOpen, setIsNewTaskModalOpen] = useState(false);
  const [decisionModalTask, setDecisionModalTask] = useState<{
    task: WorkflowTaskItem;
    decision: "approved" | "rejected";
  } | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [notification, setNotification] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Form states: New Task
  const [selectedDocId, setSelectedDocId] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDesc, setTaskDesc] = useState("");
  const [taskAssignee, setTaskAssignee] = useState("raj.patel@acrocorp.com");
  const [taskPriority, setTaskPriority] = useState("normal");

  const showNotification = (message: string, type: "success" | "error" = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [tasksRes, docsRes] = await Promise.all([
        apiClient.listWorkflowTasks(statusFilter === "all" ? undefined : statusFilter),
        apiClient.listDocuments(),
      ]);
      setTasks(tasksRes);
      setDocuments(docsRes);
      if (docsRes.length > 0 && !selectedDocId) {
        setSelectedDocId(docsRes[0].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load workflow tasks";
      showNotification(msg, "error");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, selectedDocId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handlers
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocId || !taskTitle.trim()) return;

    try {
      await apiClient.createWorkflowTask({
        document_id: selectedDocId,
        title: taskTitle.trim(),
        description: taskDesc.trim(),
        assigned_to_email: taskAssignee.trim(),
        priority: taskPriority,
      });
      setIsNewTaskModalOpen(false);
      setTaskTitle("");
      setTaskDesc("");
      showNotification("Workflow approval process initiated and routed to assignee.");
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create workflow task";
      showNotification(msg, "error");
    }
  };

  const handleDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!decisionModalTask || !decisionReason.trim()) return;

    try {
      await apiClient.decideWorkflowTask(
        decisionModalTask.task.id,
        decisionModalTask.decision,
        decisionReason.trim()
      );
      showNotification(
        `Task "${decisionModalTask.task.title}" marked as ${decisionModalTask.decision.toUpperCase()}. Audit event emitted.`
      );
      setDecisionModalTask(null);
      setDecisionReason("");
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit workflow decision";
      showNotification(msg, "error");
    }
  };

  const columns: Column<WorkflowTaskItem>[] = [
    {
      id: "title",
      header: "Process / Approval Task",
      accessor: (task) => (
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-600 shrink-0" />
          <div>
            <span className="font-semibold text-surface-900 block">{task.title}</span>
            <span className="text-[11px] text-surface-500 font-mono">
              Target Doc: {task.document_name || task.document_id}
            </span>
          </div>
        </div>
      ),
    },
    {
      id: "priority",
      header: "Priority",
      width: "100px",
      accessor: (task) => (
        <StatusPill
          label={task.priority.toUpperCase()}
          variant={
            task.priority === "high"
              ? "danger"
              : task.priority === "urgent"
              ? "danger"
              : "neutral"
          }
        />
      ),
    },
    {
      id: "status",
      header: "Status",
      width: "120px",
      accessor: (task) => {
        if (task.status === "approved") {
          return <StatusPill label="APPROVED" variant="success" />;
        }
        if (task.status === "rejected") {
          return <StatusPill label="REJECTED" variant="danger" />;
        }
        return <StatusPill label="PENDING REVIEW" variant="warning" />;
      },
    },
    {
      id: "submitted_by",
      header: "Submitted By",
      width: "160px",
      accessor: (task) => <span className="text-xs text-surface-600">{task.submitted_by_email}</span>,
    },
    {
      id: "assigned_to",
      header: "Assigned Reviewer",
      width: "160px",
      accessor: (task) => <span className="text-xs text-surface-700 font-medium">{task.assigned_to_email || "Unassigned"}</span>,
    },
    {
      id: "actions",
      header: "Review Decision",
      width: "170px",
      accessor: (task) => {
        if (task.status === "pending") {
          return (
            <div className="flex items-center gap-1.5">
              <Button
                variant="primary"
                size="sm"
                icon={<CheckCircle className="w-3 h-3" />}
                onClick={() => setDecisionModalTask({ task, decision: "approved" })}
              >
                Approve
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<XCircle className="w-3 h-3" />}
                onClick={() => setDecisionModalTask({ task, decision: "rejected" })}
              >
                Reject
              </Button>
            </div>
          );
        }
        return (
          <div className="text-[11px] text-surface-500">
            <span className="font-semibold block">{task.decision_by_email}</span>
            {task.decision_reason && <span className="italic truncate block max-w-xs">"{task.decision_reason}"</span>}
          </div>
        );
      },
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
        title="Process Automation & Workflows"
        breadcrumbs={[{ label: "Automation" }, { label: "Approval Processes" }]}
        badges={<StatusPill label="ENGINE: BPMN & SEC AUDIT ACTIVE" variant="success" />}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={loadData}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => setIsNewTaskModalOpen(true)}
            >
              Start Approval Process
            </Button>
          </div>
        }
      />

      {/* Filter Bar */}
      <div className="p-4 pb-0 flex items-center gap-2 border-b border-surface-200 bg-white">
        {["all", "pending", "approved", "rejected"].map((st) => (
          <button
            key={st}
            onClick={() => setStatusFilter(st)}
            className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-colors uppercase tracking-wider ${
              statusFilter === st
                ? "border-brand-900 text-brand-900"
                : "border-transparent text-surface-500 hover:text-surface-800"
            }`}
          >
            {st}
          </button>
        ))}
      </div>

      <div className="flex-1 p-4 overflow-auto">
        <div className="bg-white rounded-lg border border-surface-200 shadow-xs overflow-hidden">
          <DataTable
            columns={columns}
            data={tasks}
            keyExtractor={(task) => task.id}
            isLoading={isLoading}
            emptyMessage="No workflow approval tasks match your criteria."
          />
        </div>
      </div>

      {/* Modal: New Process Task */}
      <Modal
        open={isNewTaskModalOpen}
        onOpenChange={setIsNewTaskModalOpen}
        title="Initiate Document Approval Process"
        description="Submits an enterprise document to designated reviewer for formal governance sign-off."
      >
        <form onSubmit={handleCreateTask} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Target Document</label>
            <select
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.classification})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Process Title</label>
            <input
              type="text"
              required
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              placeholder="e.g. Approve Q3 Financial Statement for External Filing"
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Assigned Reviewer Email</label>
              <input
                type="email"
                required
                value={taskAssignee}
                onChange={(e) => setTaskAssignee(e.target.value)}
                placeholder="raj.patel@acrocorp.com"
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-700 mb-1">Priority</label>
              <select
                value={taskPriority}
                onChange={(e) => setTaskPriority(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
              >
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Instructions for Reviewer</label>
            <textarea
              rows={2}
              value={taskDesc}
              onChange={(e) => setTaskDesc(e.target.value)}
              placeholder="Verify section 4 compliance statements before giving final sign-off..."
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsNewTaskModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={!taskTitle.trim() || !selectedDocId}>
              Initiate Process
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Decision Reason */}
      <Modal
        open={decisionModalTask !== null}
        onOpenChange={(open) => !open && setDecisionModalTask(null)}
        title={
          decisionModalTask?.decision === "approved"
            ? "Approve Document Process"
            : "Reject Document Process"
        }
        description="Statutory audit requirement: you must provide a justification reason that will be permanently stored on the audit ledger."
      >
        <form onSubmit={handleDecision} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">
              Decision Justification (Mandatory)
            </label>
            <textarea
              rows={3}
              required
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
              placeholder={
                decisionModalTask?.decision === "approved"
                  ? "e.g. Verified figures against General Ledger; all disclosures match standard..."
                  : "e.g. Missing executive signatures on exhibit B; revise and resubmit..."
              }
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded bg-white"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setDecisionModalTask(null)}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant={decisionModalTask?.decision === "approved" ? "primary" : "danger"}
              size="sm"
              disabled={!decisionReason.trim()}
            >
              Submit Formal Decision
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default WorkflowView;
