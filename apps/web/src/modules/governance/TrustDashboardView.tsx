import React from "react";
import { ShieldCheck, Lock, Activity, CheckCircle2, AlertTriangle, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";

export const TrustDashboardView: React.FC = () => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Elixir Trust Layer Dashboard"
        breadcrumbs={[{ label: "Governance" }, { label: "Trust & Guardrails" }]}
        badges={<StatusPill label="POLICY ENFORCEMENT: ACTIVE" variant="success" />}
        actions={
          <Button variant="secondary" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />}>
            Verify Audit Chain Now
          </Button>
        }
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Trust Pillars */}
        <div className="grid grid-cols-3 gap-6">
          {/* Policy Enforcement Point (PEP) */}
          <div className="p-5 bg-white border border-surface-200 rounded-lg shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-surface-900 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-brand-600" /> Policy Enforcement Point (PEP)
              </span>
              <StatusPill label="100% ROUTE COVERAGE" variant="success" />
            </div>
            <p className="text-xs text-surface-600">
              Zero unauthenticated or uninspected paths. Every protected route passes through OPA Rego decision logic.
            </p>
            <div className="pt-2 border-t border-surface-100 flex items-center justify-between text-xs font-mono text-surface-500">
              <span>Decisions Evaluated (24h):</span>
              <span className="font-semibold text-surface-900">41,209</span>
            </div>
          </div>

          {/* Cryptographic Audit Chain */}
          <div className="p-5 bg-white border border-surface-200 rounded-lg shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-surface-900 flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-600" /> Immutable Audit Ledger
              </span>
              <StatusPill label="CHAIN INTEGRITY OK" variant="success" />
            </div>
            <p className="text-xs text-surface-600">
              Append-only SHA-256 linear hash chain. Verified with zero tampering or broken links across tenants.
            </p>
            <div className="pt-2 border-t border-surface-100 flex items-center justify-between text-xs font-mono text-surface-500">
              <span>Last Verification:</span>
              <span className="font-semibold text-surface-900">14:00 UTC (100% Valid)</span>
            </div>
          </div>

          {/* Guardrails & Antimalware */}
          <div className="p-5 bg-white border border-surface-200 rounded-lg shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm text-surface-900 flex items-center gap-2">
                <Activity className="w-4 h-4 text-brand-600" /> Ingestion Guardrails
              </span>
              <StatusPill label="CLAMAV ENGINE READY" variant="success" />
            </div>
            <p className="text-xs text-surface-600">
              Pre-ingestion magic bytes verification, archive decompression ratio limits, and isolated quarantine bucket staging.
            </p>
            <div className="pt-2 border-t border-surface-100 flex items-center justify-between text-xs font-mono text-surface-500">
              <span>Threats Intercepted (30d):</span>
              <span className="font-semibold text-status-danger">3 Malware Signatures</span>
            </div>
          </div>
        </div>

        {/* Security Events Log */}
        <div className="bg-white border border-surface-200 rounded-lg p-5 shadow-sm space-y-3">
          <h2 className="text-sm font-bold text-surface-900">Recent Security & Policy Events</h2>
          <div className="divide-y divide-surface-100 text-xs">
            <div className="py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span className="font-mono text-surface-500">14:22:01</span>
                <span className="text-surface-800">
                  User <strong className="text-surface-900">sarah.chen@acrocorp.com</strong> checked out document <strong>MSA_2026.pdf</strong> (Clearance Level 2 verified)
                </span>
              </div>
              <StatusPill label="POLICY ALLOW" variant="success" />
            </div>

            <div className="py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4 text-status-danger shrink-0" />
                <span className="font-mono text-surface-500">13:45:19</span>
                <span className="text-surface-800">
                  Attempted deletion of <strong>Vendor_Agreement_AC.pdf</strong> rejected: active legal hold <strong>#891</strong>
                </span>
              </div>
              <StatusPill label="POLICY DENY" variant="danger" />
            </div>

            <div className="py-2.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span className="font-mono text-surface-500">12:10:05</span>
                <span className="text-surface-800">
                  Automated retention check completed: 18 items transitioned to disposition queue
                </span>
              </div>
              <StatusPill label="AUDIT RECORDED" variant="neutral" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
