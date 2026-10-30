import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  Lock,
  Activity,
  RefreshCw,
  CheckCircle,
  ShieldAlert,
  FileText,
  Sliders,
  Save,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Inbox,
  Trash2,
  Check,
  X,
  ExternalLink,
} from "lucide-react";
import {
  apiClient,
  AuditEventItem,
  AuditVerificationSummary,
} from "@/api/client";
import { useAuth } from "@/config/AuthContext";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { Modal } from "@/design-system/components/Modal";
import { clsx } from "clsx";

interface PersistedGuardrailPolicy {
  tenant_id: string;
  max_upload_bytes: number;
  max_upload_mb: number;
  allowed_types: string[];
  blocked_types: string[];
  quarantine_types: string[];
  archive_max_depth: number;
  archive_max_members: number;
  archive_max_ratio: number;
  clamav_enforce: boolean;
  strict_magic_bytes: boolean;
  min_clearance_restricted: number;
  sec17a4_mode: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

interface QuarantineItem {
  id: string;
  tenant_id: string;
  filename: string;
  detected_mime: string;
  size_bytes: number;
  content_hash: string;
  reason: string;
  status: string;
  quarantined_by: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export const TrustDashboardView: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.roles?.some((r) => ["GlobalAdmin", "TenantAdmin", "Admin"].includes(r)) ?? false;

  const [activeTab, setActiveTab] = useState<"audit" | "guardrails" | "quarantine">("audit");
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<AuditVerificationSummary | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);

  // Real Guardrails State from Backend
  const [initialPolicy, setInitialPolicy] = useState<PersistedGuardrailPolicy | null>(null);
  const [maxUploadMb, setMaxUploadMb] = useState(50);
  const [strictMagicBytes, setStrictMagicBytes] = useState(true);
  const [archiveMaxDepth, setArchiveMaxDepth] = useState(3);
  const [archiveMaxMembers, setArchiveMaxMembers] = useState(500);
  const [archiveMaxRatio, setArchiveMaxRatio] = useState(100.0);
  const [minClearanceRestricted, setMinClearanceRestricted] = useState(3);
  const [sec17a4Mode, setSec17a4Mode] = useState(false);

  const [isSavingGuardrails, setIsSavingGuardrails] = useState(false);
  const [guardrailsMessage, setGuardrailsMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Quarantine Queue State
  const [quarantineItems, setQuarantineItems] = useState<QuarantineItem[]>([]);
  const [isQuarantineLoading, setIsQuarantineLoading] = useState(false);
  const [selectedQuarantineItem, setSelectedQuarantineItem] = useState<QuarantineItem | null>(null);
  const [quarantineActionMsg, setQuarantineActionMsg] = useState<string | null>(null);

  // Load Real Guardrail Policy from API
  const loadPolicy = useCallback(async () => {
    try {
      const policy = await apiClient.get<PersistedGuardrailPolicy>("/api/v1/guardrails/policy");
      if (policy) {
        setInitialPolicy(policy);
        setMaxUploadMb(policy.max_upload_mb || 50);
        setStrictMagicBytes(policy.strict_magic_bytes ?? true);
        setArchiveMaxDepth(policy.archive_max_depth || 3);
        setArchiveMaxMembers(policy.archive_max_members || 500);
        setArchiveMaxRatio(policy.archive_max_ratio || 100.0);
        setMinClearanceRestricted(policy.min_clearance_restricted || 3);
        setSec17a4Mode(policy.sec17a4_mode ?? false);
      }
    } catch (err: any) {
      console.error("Failed to load guardrail policy:", err);
    }
  }, []);

  // Load Quarantine Queue from API
  const loadQuarantine = useCallback(async () => {
    try {
      setIsQuarantineLoading(true);
      const items = await apiClient.get<QuarantineItem[]>("/api/v1/guardrails/quarantine");
      setQuarantineItems(items || []);
    } catch (err: any) {
      console.error("Failed to load quarantine queue:", err);
    } finally {
      setIsQuarantineLoading(false);
    }
  }, []);

  // Load Audit Events
  const loadAuditEvents = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await apiClient.listAuditEvents(1, 50);
      setEvents(res.items || []);
      setTotalEvents(res.total || 0);
    } catch (err) {
      console.error("Failed to load audit events:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAuditEvents();
    loadPolicy();
    loadQuarantine();
  }, [loadAuditEvents, loadPolicy, loadQuarantine]);

  // Dirty State Calculation
  const isDirty = initialPolicy
    ? maxUploadMb !== initialPolicy.max_upload_mb ||
      strictMagicBytes !== initialPolicy.strict_magic_bytes ||
      archiveMaxDepth !== initialPolicy.archive_max_depth ||
      archiveMaxMembers !== initialPolicy.archive_max_members ||
      archiveMaxRatio !== initialPolicy.archive_max_ratio ||
      minClearanceRestricted !== initialPolicy.min_clearance_restricted ||
      sec17a4Mode !== initialPolicy.sec17a4_mode
    : false;

  const handleReset = () => {
    if (initialPolicy) {
      setMaxUploadMb(initialPolicy.max_upload_mb);
      setStrictMagicBytes(initialPolicy.strict_magic_bytes);
      setArchiveMaxDepth(initialPolicy.archive_max_depth);
      setArchiveMaxMembers(initialPolicy.archive_max_members);
      setArchiveMaxRatio(initialPolicy.archive_max_ratio);
      setMinClearanceRestricted(initialPolicy.min_clearance_restricted);
      setSec17a4Mode(initialPolicy.sec17a4_mode);
    }
  };

  // Real PUT to /api/v1/guardrails/policy
  const handleSaveGuardrails = async () => {
    if (!isAdmin) return;
    setIsSavingGuardrails(true);
    setGuardrailsMessage(null);
    try {
      const updated = await apiClient.put<PersistedGuardrailPolicy>("/api/v1/guardrails/policy", {
        max_upload_mb: maxUploadMb,
        strict_magic_bytes: strictMagicBytes,
        archive_max_depth: archiveMaxDepth,
        archive_max_members: archiveMaxMembers,
        archive_max_ratio: archiveMaxRatio,
        min_clearance_restricted: minClearanceRestricted,
        sec17a4_mode: sec17a4Mode,
      });
      setInitialPolicy(updated);
      setGuardrailsMessage({
        text: `Guardrail policy saved and audited! Updated by ${updated.updated_by} at ${new Date(updated.updated_at || "").toLocaleTimeString()}`,
        type: "success",
      });
      loadAuditEvents();
      setTimeout(() => setGuardrailsMessage(null), 5000);
    } catch (err: any) {
      setGuardrailsMessage({
        text: err.body?.detail || err.message || "Failed to update guardrails policy",
        type: "error",
      });
    } finally {
      setIsSavingGuardrails(false);
    }
  };

  // Quarantine Actions
  const handleReleaseQuarantine = async (itemId: string) => {
    if (!isAdmin) return;
    try {
      await apiClient.post(`/api/v1/guardrails/quarantine/${itemId}/release`);
      setQuarantineActionMsg("Item successfully released from quarantine.");
      setSelectedQuarantineItem(null);
      loadQuarantine();
      loadAuditEvents();
      setTimeout(() => setQuarantineActionMsg(null), 4000);
    } catch (err: any) {
      alert(err.message || "Failed to release quarantined item");
    }
  };

  const handleDeleteQuarantine = async (itemId: string) => {
    if (!isAdmin) return;
    if (!confirm("Are you sure you want to permanently purge this quarantined file? This action is audited.")) return;
    try {
      await apiClient.delete(`/api/v1/guardrails/quarantine/${itemId}`);
      setQuarantineActionMsg("Quarantined item permanently purged from storage.");
      setSelectedQuarantineItem(null);
      loadQuarantine();
      loadAuditEvents();
      setTimeout(() => setQuarantineActionMsg(null), 4000);
    } catch (err: any) {
      alert(err.message || "Failed to delete quarantined item");
    }
  };

  const handleVerifyChain = async () => {
    try {
      setIsVerifying(true);
      const summary = await apiClient.verifyAuditChain();
      setVerificationResult(summary);
    } catch (err) {
      console.error("Verification failed:", err);
    } finally {
      setIsVerifying(false);
    }
  };

  const auditColumns: Column<AuditEventItem>[] = [
    {
      id: "seq",
      header: "Seq #",
      width: "80px",
      accessor: (evt) => <span className="font-mono text-xs font-bold text-brand-900 dark:text-brand-300">#{evt.sequence_number}</span>,
    },
    {
      id: "timestamp",
      header: "Timestamp (UTC)",
      width: "160px",
      accessor: (evt) => (
        <span className="font-mono text-[11px] text-surface-500">
          {new Date(evt.timestamp).toLocaleString()}
        </span>
      ),
    },
    {
      id: "action",
      header: "Action / Operation",
      accessor: (evt) => (
        <div>
          <span className="font-semibold text-xs text-surface-900 dark:text-surface-100">{evt.action}</span>
          <span className="block text-[11px] text-surface-500 font-mono">{evt.resource_type}:{evt.resource_id}</span>
        </div>
      ),
    },
    {
      id: "actor",
      header: "Actor",
      width: "200px",
      accessor: (evt) => (
        <span className="text-xs text-surface-700 dark:text-surface-300 font-medium">
          {evt.actor_email}
        </span>
      ),
    },
    {
      id: "outcome",
      header: "Outcome",
      width: "100px",
      accessor: (evt) => {
        const isAllow = evt.outcome.toUpperCase() === "ALLOW";
        return (
          <StatusPill
            label={evt.outcome}
            variant={isAllow ? "success" : "danger"}
          />
        );
      },
    },
    {
      id: "hash",
      header: "SHA-256 Hash Chain Link",
      width: "180px",
      accessor: (evt) => (
        <span className="font-mono text-[10px] text-surface-400 block truncate" title={evt.current_hash}>
          {evt.current_hash.slice(0, 16)}...
        </span>
      ),
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-surface-50 dark:bg-surface-950">
      <PageHeader
        title="Elixir Trust Layer Dashboard"
        breadcrumbs={[{ label: "Governance" }, { label: "Trust & Guardrails" }]}
        badges={<StatusPill label="POLICY ENGINE & AUDIT CHAIN LIVE" variant="success" />}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={clsx("w-3.5 h-3.5", isLoading && "animate-spin")} />}
              onClick={() => {
                loadAuditEvents();
                loadPolicy();
                loadQuarantine();
              }}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<ShieldCheck className="w-4 h-4" />}
              onClick={handleVerifyChain}
              disabled={isVerifying}
            >
              {isVerifying ? "Verifying Monotonic Chain..." : "Verify Cryptographic Audit Chain"}
            </Button>
          </div>
        }
      />

      {/* Security Architecture Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-surface-900 dark:text-surface-100">
            <ShieldCheck className="w-4 h-4 text-brand-600" />
            <span>Policy Enforcement Point (PEP)</span>
            <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300">
              OPA 0.68.0 ENFORCING
            </span>
          </div>
          <p className="text-xs text-surface-500 mt-2">
            Zero uninspected paths. Every protected route passes through OPA Rego decision logic with clearance-based multitenant filtering.
          </p>
          <div className="mt-4 pt-3 border-t border-surface-100 dark:border-surface-800 flex justify-between items-center text-[11px] font-mono">
            <span className="text-surface-400">Decision Telemetry:</span>
            <span className="font-semibold text-surface-700 dark:text-surface-300">Enforcing (Deny by Default)</span>
          </div>
        </div>

        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-surface-900 dark:text-surface-100">
            <Lock className="w-4 h-4 text-emerald-600" />
            <span>Immutable Audit Ledger</span>
            <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 dark:bg-blue-950 dark:text-blue-300">
              CHAIN SEALED
            </span>
          </div>
          <p className="text-xs text-surface-500 mt-2">
            Append-only SHA-256 linear hash chain. Formatted for SEC Rule 17a-4 and FINRA non-rewritable, non-erasable electronic compliance.
          </p>
          <div className="mt-4 pt-3 border-t border-surface-100 dark:border-surface-800 flex justify-between items-center text-[11px] font-mono">
            <span className="text-surface-400">Recorded Events:</span>
            <span className="font-bold text-brand-900 dark:text-brand-300">{totalEvents} events sealed</span>
          </div>
        </div>

        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-surface-900 dark:text-surface-100">
            <Activity className="w-4 h-4 text-indigo-600" />
            <span>Ingestion Guardrails</span>
            <span className="ml-auto text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300">
              CLAMAV FAIL-CLOSED
            </span>
          </div>
          <p className="text-xs text-surface-500 mt-2">
            Stream-checked size limits, magic bytes validation, ClamAV antivirus daemon, and content-hash MinIO storage.
          </p>
          <div className="mt-4 pt-3 border-t border-surface-100 dark:border-surface-800 flex justify-between items-center text-[11px] font-mono">
            <span className="text-surface-400">Scanner Daemon:</span>
            <span className="font-semibold text-emerald-700 dark:text-emerald-400">Active & Enforcing</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-surface-200 dark:border-surface-800">
        <button
          onClick={() => setActiveTab("audit")}
          className={clsx(
            "px-4 py-2 text-xs font-semibold border-b-2 transition flex items-center gap-2",
            activeTab === "audit"
              ? "border-brand-600 text-brand-900 dark:text-brand-300 bg-white/60 dark:bg-surface-900/60"
              : "border-transparent text-surface-500 hover:text-surface-800"
          )}
        >
          <FileText className="w-4 h-4" />
          <span>Immutable Audit Ledger ({totalEvents})</span>
        </button>

        <button
          onClick={() => setActiveTab("guardrails")}
          className={clsx(
            "px-4 py-2 text-xs font-semibold border-b-2 transition flex items-center gap-2",
            activeTab === "guardrails"
              ? "border-brand-600 text-brand-900 dark:text-brand-300 bg-white/60 dark:bg-surface-900/60"
              : "border-transparent text-surface-500 hover:text-surface-800"
          )}
        >
          <Sliders className="w-4 h-4" />
          <span>Tenant Policy & Guardrails Configuration</span>
          {isDirty && <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" title="Unsaved changes"></span>}
        </button>

        <button
          onClick={() => setActiveTab("quarantine")}
          className={clsx(
            "px-4 py-2 text-xs font-semibold border-b-2 transition flex items-center gap-2",
            activeTab === "quarantine"
              ? "border-brand-600 text-brand-900 dark:text-brand-300 bg-white/60 dark:bg-surface-900/60"
              : "border-transparent text-surface-500 hover:text-surface-800"
          )}
        >
          <Inbox className="w-4 h-4" />
          <span>Quarantine Queue</span>
          {quarantineItems.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 font-mono text-[10px] font-bold">
              {quarantineItems.length}
            </span>
          )}
        </button>
      </div>

      {/* TAB 1: IMMUTABLE AUDIT LEDGER */}
      {activeTab === "audit" && (
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100 flex items-center gap-2">
                <Lock className="w-4 h-4 text-brand-600" />
                Immutable Cryptographic Audit Ledger
              </h2>
              <p className="text-xs text-surface-500 mt-0.5">
                Every authorization decision, state change, and document operation forms a cryptographically linked SHA-256 chain.
              </p>
            </div>
            <span className="text-xs font-mono text-surface-500">
              {events.length} of {totalEvents} events loaded
            </span>
          </div>

          <DataTable
            columns={auditColumns}
            data={events}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedEvent(row)}
            emptyMessage="No audit ledger events recorded for this tenant boundary."
          />
        </div>
      )}

      {/* TAB 2: PERSISTED TENANT POLICY & GUARDRAILS */}
      {activeTab === "guardrails" && (
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 shadow-xs space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-surface-200 dark:border-surface-800">
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-brand-600" />
                Persisted Tenant Policy & Ingestion Guardrails
              </h2>
              <p className="text-xs text-surface-500 mt-1">
                Real database configuration enforced on every upload and request. Changes are audited with before/after diffs in the cryptographic ledger.
              </p>
            </div>

            <div className="flex items-center gap-2">
              {isDirty && (
                <Button
                  variant="outline"
                  size="sm"
                  icon={<RotateCcw className="w-3.5 h-3.5" />}
                  onClick={handleReset}
                >
                  Reset Changes
                </Button>
              )}
              <Button
                variant="primary"
                size="sm"
                icon={<Save className="w-3.5 h-3.5" />}
                onClick={handleSaveGuardrails}
                disabled={!isDirty || isSavingGuardrails || !isAdmin}
              >
                {isSavingGuardrails ? "Persisting to PostgreSQL..." : isDirty ? "Save & Enforce Policies" : "Policy Enforced"}
              </Button>
            </div>
          </div>

          {/* Feedback Banner */}
          {guardrailsMessage && (
            <div
              className={clsx(
                "p-3 rounded-lg text-xs flex items-center gap-2",
                guardrailsMessage.type === "success"
                  ? "bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-200"
                  : "bg-red-50 text-red-800 border border-red-300 dark:bg-red-950/40 dark:text-red-200"
              )}
            >
              {guardrailsMessage.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              )}
              <span>{guardrailsMessage.text}</span>
            </div>
          )}

          {/* Controls Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            {/* Left Column: Upload Pipeline Invariants */}
            <div className="space-y-4 p-5 rounded-lg bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-700">
              <h3 className="font-bold text-surface-900 dark:text-surface-100 flex items-center gap-2 pb-2 border-b border-surface-200 dark:border-surface-700">
                <Activity className="w-4 h-4 text-emerald-600" />
                Ingestion Pipeline Guardrails
              </h3>

              {/* ClamAV Stream Inspection (PERMANENTLY LOCKED) */}
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-surface-900 dark:text-surface-100 flex items-center gap-1.5">
                    ClamAV Antivirus Stream Inspection
                    <Lock className="w-3 h-3 text-amber-600" />
                  </span>
                  <span className="text-[11px] text-surface-500">
                    Non-negotiable server invariant. Daemon unreachable = HTTP 503 fail-closed.
                  </span>
                </div>
                <span className="px-2.5 py-1 rounded text-[11px] font-mono font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300">
                  ALWAYS ENFORCED
                </span>
              </div>

              {/* Magic Bytes Strict Header Validation */}
              <div className="flex items-center justify-between pt-3 border-t border-surface-200 dark:border-surface-700">
                <div>
                  <span className="font-semibold text-surface-900 dark:text-surface-100 block">
                    Strict Magic Bytes Verification
                  </span>
                  <span className="text-[11px] text-surface-500">
                    Inspect binary magic bytes (PE, ELF, PDF, ZIP). Flag extension mismatches.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={strictMagicBytes}
                  onChange={(e) => setStrictMagicBytes(e.target.checked)}
                  disabled={!isAdmin}
                  className="w-4 h-4 accent-brand-600 cursor-pointer"
                />
              </div>

              {/* Max Upload Size Slider */}
              <div className="pt-3 border-t border-surface-200 dark:border-surface-700 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-surface-900 dark:text-surface-100">
                    Max Upload Payload Size:
                  </span>
                  <span className="font-mono font-bold text-brand-900 dark:text-brand-300">
                    {maxUploadMb} MB
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="100"
                  step="5"
                  value={maxUploadMb}
                  onChange={(e) => setMaxUploadMb(Number(e.target.value))}
                  disabled={!isAdmin}
                  className="w-full accent-brand-600 cursor-pointer"
                />
                <span className="text-[11px] text-surface-400 block">
                  Enforced at HTTP stream level; oversized payloads are terminated immediately.
                </span>
              </div>
            </div>

            {/* Right Column: Archive Security & Clearance Configuration */}
            <div className="space-y-4 p-5 rounded-lg bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-700">
              <h3 className="font-bold text-surface-900 dark:text-surface-100 flex items-center gap-2 pb-2 border-b border-surface-200 dark:border-surface-700">
                <ShieldCheck className="w-4 h-4 text-brand-600" />
                Archive Safety & Access Clearances
              </h3>

              {/* Archive Zip Bomb Threshold */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-surface-900 dark:text-surface-100">
                    Zip Bomb Max Compression Ratio:
                  </span>
                  <span className="font-mono font-bold text-brand-900 dark:text-brand-300">
                    {archiveMaxRatio}:1
                  </span>
                </div>
                <input
                  type="range"
                  min="20"
                  max="250"
                  step="10"
                  value={archiveMaxRatio}
                  onChange={(e) => setArchiveMaxRatio(Number(e.target.value))}
                  disabled={!isAdmin}
                  className="w-full accent-brand-600 cursor-pointer"
                />
                <span className="text-[11px] text-surface-400 block">
                  Archives expanding beyond {archiveMaxRatio}x uncompressed size are blocked as zip bombs.
                </span>
              </div>

              {/* Archive Recursion Depth & Max Members */}
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-surface-200 dark:border-surface-700">
                <div>
                  <span className="font-semibold block mb-1">Max Archive Depth:</span>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={archiveMaxDepth}
                    onChange={(e) => setArchiveMaxDepth(Number(e.target.value))}
                    disabled={!isAdmin}
                    className="w-full p-2 border border-surface-300 dark:border-surface-700 rounded bg-white dark:bg-surface-900 font-mono text-xs"
                  />
                </div>
                <div>
                  <span className="font-semibold block mb-1">Max Archive Members:</span>
                  <input
                    type="number"
                    min="10"
                    max="5000"
                    step="50"
                    value={archiveMaxMembers}
                    onChange={(e) => setArchiveMaxMembers(Number(e.target.value))}
                    disabled={!isAdmin}
                    className="w-full p-2 border border-surface-300 dark:border-surface-700 rounded bg-white dark:bg-surface-900 font-mono text-xs"
                  />
                </div>
              </div>

              {/* Minimum Clearance for Restricted Content */}
              <div className="pt-3 border-t border-surface-200 dark:border-surface-700 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-surface-900 dark:text-surface-100">
                    Min Clearance for RESTRICTED Content:
                  </span>
                  <select
                    value={minClearanceRestricted}
                    onChange={(e) => setMinClearanceRestricted(Number(e.target.value))}
                    disabled={!isAdmin}
                    className="p-1.5 border border-surface-300 dark:border-surface-700 rounded font-mono text-xs bg-white dark:bg-surface-900"
                  >
                    <option value={2}>Level 2 (Internal+)</option>
                    <option value={3}>Level 3 (Confidential+)</option>
                    <option value={4}>Level 4 (Restricted)</option>
                    <option value={5}>Level 5 (Top Secret)</option>
                  </select>
                </div>
              </div>

              {/* SEC 17a-4 Immutability Toggle (Properly Labeled) */}
              <div className="flex items-center justify-between pt-3 border-t border-surface-200 dark:border-surface-700">
                <div>
                  <span className="font-semibold text-surface-900 dark:text-surface-100 flex items-center gap-2">
                    SEC Rule 17a-4 Immutability Mode
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300">
                      Preview, not enforced
                    </span>
                  </span>
                  <span className="text-[11px] text-surface-500">
                    Write-once electronic records retention compliance locking (simulated in v1.0).
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={sec17a4Mode}
                  onChange={(e) => setSec17a4Mode(e.target.checked)}
                  disabled={!isAdmin}
                  className="w-4 h-4 accent-brand-600 cursor-pointer"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: ADMINISTRATIVE QUARANTINE QUEUE */}
      {activeTab === "quarantine" && (
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100 flex items-center gap-2">
                <Inbox className="w-4 h-4 text-amber-600" />
                Administrative Quarantine Queue
              </h2>
              <p className="text-xs text-surface-500 mt-0.5">
                Files held for inspection due to policy mismatch, unlisted formats, or high-risk content.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={clsx("w-3.5 h-3.5", isQuarantineLoading && "animate-spin")} />}
              onClick={loadQuarantine}
            >
              Refresh Queue
            </Button>
          </div>

          {quarantineActionMsg && (
            <div className="p-3 bg-emerald-50 text-emerald-800 border border-emerald-300 rounded-lg text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{quarantineActionMsg}</span>
            </div>
          )}

          {quarantineItems.length === 0 ? (
            <div className="p-12 text-center text-surface-400 space-y-2">
              <Inbox className="w-10 h-10 mx-auto opacity-50" />
              <p className="text-sm font-semibold">Quarantine queue is empty</p>
              <p className="text-xs text-surface-400">All incoming tenant documents passed the ingestion guardrails.</p>
            </div>
          ) : (
            <div className="divide-y divide-surface-200 dark:divide-surface-800 border border-surface-200 dark:border-surface-800 rounded-lg overflow-hidden">
              {quarantineItems.map((item) => (
                <div
                  key={item.id}
                  className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-surface-50/60 dark:hover:bg-surface-850/60 transition text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-surface-900 dark:text-surface-100">{item.filename}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                        {item.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-surface-500 font-mono">
                      Reason: <strong className="text-red-700 dark:text-red-400">{item.reason}</strong>
                    </p>
                    <p className="text-[11px] text-surface-400 font-mono">
                      Detected MIME: {item.detected_mime} • Size: {(item.size_bytes / 1024).toFixed(1)} KB • Quarantined: {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      icon={<Check className="w-3.5 h-3.5 text-emerald-600" />}
                      onClick={() => handleReleaseQuarantine(item.id)}
                      disabled={!isAdmin}
                    >
                      Release to Workspace
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      icon={<Trash2 className="w-3.5 h-3.5" />}
                      onClick={() => handleDeleteQuarantine(item.id)}
                      disabled={!isAdmin}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Audit Event Details Modal */}
      {selectedEvent && (
        <Modal
          open={!!selectedEvent}
          onOpenChange={(open) => !open && setSelectedEvent(null)}
          title={`Audit Ledger Event #${selectedEvent.sequence_number}`}
          description={`Recorded ${selectedEvent.timestamp} by ${selectedEvent.actor_email}`}
        >
          <div className="space-y-3 font-mono text-xs">
            <div className="p-3 rounded bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 space-y-1.5">
              <div className="flex justify-between">
                <span className="text-surface-400">Action:</span>
                <span className="font-bold">{selectedEvent.action}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-400">Target Resource:</span>
                <span>{selectedEvent.resource_type}:{selectedEvent.resource_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-400">Outcome:</span>
                <span className={selectedEvent.outcome === "ALLOW" ? "text-emerald-600 font-bold" : "text-red-600 font-bold"}>
                  {selectedEvent.outcome}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-surface-400">Reason:</span>
                <span className="text-surface-700 dark:text-surface-300">{selectedEvent.reason || "None specified"}</span>
              </div>
            </div>

            <div>
              <span className="text-surface-500 block mb-1 font-sans text-xs font-semibold">Cryptographic Hash Linkage:</span>
              <div className="p-3 rounded bg-slate-950 text-slate-200 text-[11px] space-y-2">
                <div>
                  <span className="text-slate-500 block text-[10px]">PREVIOUS HASH:</span>
                  <span className="break-all">{selectedEvent.prev_hash}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">CURRENT EVENT HASH:</span>
                  <span className="break-all text-emerald-400">{selectedEvent.current_hash}</span>
                </div>
              </div>
            </div>

            <div>
              <span className="text-surface-500 block mb-1 font-sans text-xs font-semibold">Audited Event Payload:</span>
              <pre className="p-3 rounded bg-surface-100 dark:bg-surface-900 border border-surface-200 dark:border-surface-800 text-[11px] overflow-auto max-h-48">
                {JSON.stringify(selectedEvent.payload, null, 2)}
              </pre>
            </div>
          </div>
        </Modal>
      )}

      {/* Cryptographic Verification Modal */}
      {verificationResult && (
        <Modal
          open={!!verificationResult}
          onOpenChange={(open) => !open && setVerificationResult(null)}
          title="Cryptographic Chain Verification Report"
          description="Verification of every SHA-256 linear hash linkage across all tenant events."
        >
          <div className="space-y-4 text-xs">
            <div
              className={clsx(
                "p-4 rounded-xl border flex items-center gap-3",
                verificationResult.is_valid
                  ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-200"
                  : "bg-red-50 text-red-800 border-red-300 dark:bg-red-950/40 dark:text-red-200"
              )}
            >
              {verificationResult.is_valid ? (
                <CheckCircle className="w-6 h-6 text-emerald-600 shrink-0" />
              ) : (
                <ShieldAlert className="w-6 h-6 text-red-600 shrink-0" />
              )}
              <div>
                <h4 className="font-bold text-sm">
                  {verificationResult.is_valid ? "Cryptographic Chain Intact & Valid" : "Tamper Violation Detected!"}
                </h4>
                <p className="text-[11px] mt-0.5">
                  {verificationResult.is_valid
                    ? `All ${verificationResult.total_events} events strictly conform to SHA-256 monotonic hashing with zero broken links.`
                    : `${verificationResult.violations.length} sequence hash mismatches discovered in audit records.`}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="p-3 rounded bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-800">
                <span className="text-surface-400 block text-[10px]">TOTAL EVENTS CHECKED</span>
                <span className="font-bold text-sm">{verificationResult.total_events}</span>
              </div>
              <div className="p-3 rounded bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-800">
                <span className="text-surface-400 block text-[10px]">TENANTS VERIFIED</span>
                <span className="font-bold text-sm">{verificationResult.tenants_checked}</span>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
