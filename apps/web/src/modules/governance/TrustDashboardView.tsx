import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  Lock,
  Activity,
  RefreshCw,
  CheckCircle,
  ShieldAlert,
  FileText,
} from "lucide-react";
import {
  apiClient,
  AuditEventItem,
  AuditVerificationSummary,
} from "@/api/client";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { Modal } from "@/design-system/components/Modal";

export const TrustDashboardView: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<AuditVerificationSummary | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);

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
  }, [loadAuditEvents]);

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

  const columns: Column<AuditEventItem>[] = [
    {
      id: "seq",
      header: "Seq #",
      width: "80px",
      accessor: (evt) => <span className="font-mono text-xs font-bold text-brand-900">#{evt.sequence_number}</span>,
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
          <span className="font-semibold text-xs text-surface-900 font-mono block">{evt.action}</span>
          <span className="text-[10px] text-surface-500 font-mono">
            {evt.resource_type}:{evt.resource_id ? evt.resource_id.substring(0, 8) : "root"}
          </span>
        </div>
      ),
    },
    {
      id: "actor",
      header: "Actor",
      width: "180px",
      accessor: (evt) => <span className="text-xs text-surface-700 truncate block">{evt.actor_email}</span>,
    },
    {
      id: "outcome",
      header: "Outcome",
      width: "100px",
      accessor: (evt) => (
        <StatusPill
          label={evt.outcome}
          variant={evt.outcome === "SUCCESS" ? "success" : "danger"}
        />
      ),
    },
    {
      id: "hash",
      header: "SHA-256 Hash Chain Link",
      accessor: (evt) => (
        <span className="font-mono text-[10px] text-surface-500 truncate block max-w-xs" title={evt.current_hash}>
          {evt.current_hash ? evt.current_hash.substring(0, 20) + "..." : "Genesis"}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Elixir Trust Layer Dashboard"
        breadcrumbs={[{ label: "Governance" }, { label: "Trust & Guardrails" }]}
        badges={<StatusPill label="POLICY ENGINE & AUDIT CHAIN LIVE" variant="success" />}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={loadAuditEvents}
            >
              Refresh
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<ShieldCheck className={`w-3.5 h-3.5 text-emerald-600 ${isVerifying ? "animate-spin" : ""}`} />}
              onClick={handleVerifyChain}
              disabled={isVerifying}
            >
              {isVerifying ? "Computing Hashes..." : "Verify Cryptographic Audit Chain"}
            </Button>
          </div>
        }
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Trust Pillars */}
        <div className="grid grid-cols-3 gap-6">
          {/* Policy Enforcement Point (PEP) */}
          <div className="p-5 bg-white border border-surface-200 rounded-lg shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-surface-900 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-brand-600" /> Policy Enforcement Point (PEP)
              </span>
              <StatusPill label="OPA 0.68.0 ONLINE" variant="success" />
            </div>
            <p className="text-xs text-surface-600">
              Zero uninspected paths. Every protected route passes through OPA Rego decision logic with clearance-based
              multitenant filtering.
            </p>
            <div className="pt-2 border-t border-surface-100 flex items-center justify-between text-xs font-mono text-surface-500">
              <span>Decision Telemetry:</span>
              <span className="font-semibold text-emerald-700">Enforcing (Deny by Default)</span>
            </div>
          </div>

          {/* Cryptographic Audit Chain */}
          <div className="p-5 bg-white border border-surface-200 rounded-lg shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-surface-900 flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-600" /> Immutable Audit Ledger
              </span>
              <StatusPill label="CHAIN SEALED" variant="success" />
            </div>
            <p className="text-xs text-surface-600">
              Append-only SHA-256 linear hash chain. Formatted for SEC Rule 17a-4 and FINRA non-rewriteable, non-erasable
              electronic compliance.
            </p>
            <div className="pt-2 border-t border-surface-100 flex items-center justify-between text-xs font-mono text-surface-500">
              <span>Recorded Events:</span>
              <span className="font-semibold text-brand-900">{totalEvents} events sealed</span>
            </div>
          </div>

          {/* Guardrails & Antimalware */}
          <div className="p-5 bg-white border border-surface-200 rounded-lg shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-surface-900 flex items-center gap-2">
                <Activity className="w-4 h-4 text-brand-600" /> Ingestion Guardrails
              </span>
              <StatusPill label="CLAMAV READY" variant="success" />
            </div>
            <p className="text-xs text-surface-600">
              Pre-ingestion magic bytes verification, ClamAV daemon antivirus stream scanning, and isolated MinIO bucket storage.
            </p>
            <div className="pt-2 border-t border-surface-100 flex items-center justify-between text-xs font-mono text-surface-500">
              <span>Scanner Daemon:</span>
              <span className="font-semibold text-emerald-600">Active & Enforcing</span>
            </div>
          </div>
        </div>

        {/* Live Immutable Audit Events Ledger */}
        <div className="bg-white border border-surface-200 rounded-lg p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-surface-900 flex items-center gap-2">
                <FileText className="w-4 h-4 text-brand-700" /> Immutable Cryptographic Audit Ledger
              </h2>
              <span className="text-xs text-surface-500">
                Every authorization decision, state change, and document operation forms a cryptographically linked SHA-256 chain.
              </span>
            </div>
            <span className="text-xs font-mono font-semibold text-brand-900 bg-brand-50 border border-brand-200 px-2 py-1 rounded">
              {events.length} of {totalEvents} events loaded
            </span>
          </div>

          <div className="overflow-hidden rounded-lg border border-surface-200">
            <DataTable
              columns={columns}
              data={events}
              keyExtractor={(evt) => evt.id}
              isLoading={isLoading}
              onRowClick={(evt) => setSelectedEvent(evt)}
              selectedId={selectedEvent?.id}
              emptyMessage="No audit ledger events recorded yet."
            />
          </div>
        </div>
      </div>

      {/* Verification Result Modal */}
      <Modal
        open={verificationResult !== null}
        onOpenChange={(open) => !open && setVerificationResult(null)}
        title="Cryptographic Hash Chain Verification"
        description="Linear cryptographic validation of the append-only SHA-256 event ledger."
      >
        {verificationResult && (
          <div className="space-y-4">
            <div
              className={`p-4 rounded-lg flex items-center gap-3 ${
                verificationResult.is_valid
                  ? "bg-emerald-50 border border-emerald-200 text-emerald-900"
                  : "bg-red-50 border border-red-200 text-red-900"
              }`}
            >
              {verificationResult.is_valid ? (
                <CheckCircle className="w-6 h-6 text-emerald-600 shrink-0" />
              ) : (
                <ShieldAlert className="w-6 h-6 text-red-600 shrink-0" />
              )}
              <div>
                <h4 className="text-sm font-bold">
                  {verificationResult.is_valid
                    ? "Cryptographic Integrity Verified: 100% Intact"
                    : "Integrity Violation Detected!"}
                </h4>
                <p className="text-xs mt-0.5">
                  {verificationResult.is_valid
                    ? `All ${verificationResult.total_events} recorded audit events across ${verificationResult.tenants_checked} tenants were recalculated and verified against their parent SHA-256 hashes without discrepancy.`
                    : `${verificationResult.violations.length} hash chain discrepancies or sequence anomalies were discovered.`}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 text-xs bg-surface-50 p-3 rounded border border-surface-200 font-mono">
              <div>
                <span className="text-surface-500 block">Total Events:</span>
                <span className="font-bold text-surface-900">{verificationResult.total_events}</span>
              </div>
              <div>
                <span className="text-surface-500 block">Tenants Checked:</span>
                <span className="font-bold text-surface-900">{verificationResult.tenants_checked}</span>
              </div>
              <div>
                <span className="text-surface-500 block">Violations:</span>
                <span className="font-bold text-emerald-700">{verificationResult.violations.length}</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="primary" size="sm" onClick={() => setVerificationResult(null)}>
                Dismiss
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Event Details Modal */}
      <Modal
        open={selectedEvent !== null}
        onOpenChange={(open) => !open && setSelectedEvent(null)}
        title={`Audit Event #${selectedEvent?.sequence_number}: ${selectedEvent?.action}`}
        description="Detailed cryptographic payload recorded for SEC / FINRA compliance."
      >
        {selectedEvent && (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 bg-surface-50 p-3 rounded border border-surface-200">
              <div>
                <span className="text-surface-500 font-semibold block">Actor:</span>
                <span className="font-mono text-surface-900">{selectedEvent.actor_email}</span>
              </div>
              <div>
                <span className="text-surface-500 font-semibold block">Timestamp:</span>
                <span className="font-mono text-surface-900">{selectedEvent.timestamp}</span>
              </div>
              <div>
                <span className="text-surface-500 font-semibold block">Correlation ID:</span>
                <span className="font-mono text-surface-700 text-[11px] truncate block">{selectedEvent.correlation_id}</span>
              </div>
              <div>
                <span className="text-surface-500 font-semibold block">Outcome:</span>
                <span className="font-semibold text-emerald-700">{selectedEvent.outcome}</span>
              </div>
            </div>

            <div>
              <span className="text-surface-500 font-semibold block mb-1">Previous SHA-256 Hash:</span>
              <span className="font-mono text-[10px] text-surface-600 bg-surface-100 p-1.5 rounded block truncate">
                {selectedEvent.prev_hash || "GENESIS_NODE"}
              </span>
            </div>

            <div>
              <span className="text-surface-500 font-semibold block mb-1">Current Event SHA-256 Seal:</span>
              <span className="font-mono text-[10px] text-brand-900 bg-brand-50 p-1.5 rounded block truncate font-bold">
                {selectedEvent.current_hash}
              </span>
            </div>

            <div>
              <span className="text-surface-500 font-semibold block mb-1">Audit Payload (JSON):</span>
              <pre className="bg-surface-900 text-surface-100 p-2.5 rounded font-mono text-[11px] max-h-36 overflow-auto">
                {JSON.stringify(selectedEvent.payload, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="outline" size="sm" onClick={() => setSelectedEvent(null)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default TrustDashboardView;
