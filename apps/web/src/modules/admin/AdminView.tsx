import React, { useState, useEffect, useCallback } from "react";
import {
  Users,
  FileText,
  Lock,
  Clock,
  Activity,
  ShieldCheck,
  RefreshCw,
  Server,
  CheckCircle,
  UserCheck,
  UserX,
  ShieldAlert,
} from "lucide-react";
import {
  apiClient,
  AdminKPIs,
  SystemHealthReport,
  AdminUserItem,
} from "@/api/client";
import { PageHeader } from "@/components/shell/PageHeader";
import { StatusPill } from "@/design-system/components/StatusPill";
import { Button } from "@/design-system/components/Button";
import { DataTable, Column } from "@/design-system/components/DataTable";

export const AdminView: React.FC = () => {
  const [kpis, setKpis] = useState<AdminKPIs | null>(null);
  const [health, setHealth] = useState<SystemHealthReport | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const showNotification = (message: string, type: "success" | "error" = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [kpiRes, healthRes, userRes] = await Promise.all([
        apiClient.getAdminKPIs(),
        apiClient.getSystemHealth(),
        apiClient.listAdminUsers(),
      ]);
      setKpis(kpiRes);
      setHealth(healthRes);
      setUsers(userRes.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load admin telemetry";
      showNotification(msg, "error");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleToggleUserActive = async (u: AdminUserItem) => {
    try {
      const updated = await apiClient.updateAdminUser(u.id, {
        is_active: !u.is_active,
      });
      setUsers((prev) => prev.map((item) => (item.id === u.id ? updated : item)));
      showNotification(`User "${u.email}" is now ${updated.is_active ? "ACTIVE" : "SUSPENDED"}.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update user status";
      showNotification(msg, "error");
    }
  };

  const handleChangeClearance = async (u: AdminUserItem, newLevel: number) => {
    try {
      const updated = await apiClient.updateAdminUser(u.id, {
        clearance_level: newLevel,
      });
      setUsers((prev) => prev.map((item) => (item.id === u.id ? updated : item)));
      showNotification(`Clearance level for "${u.email}" updated to Level ${newLevel}.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update clearance level";
      showNotification(msg, "error");
    }
  };

  const columns: Column<AdminUserItem>[] = [
    {
      id: "name",
      header: "User Identity",
      accessor: (u) => (
        <div>
          <span className="font-semibold text-surface-900 block">
            {[u.first_name, u.last_name].filter(Boolean).join(" ") || u.username}
          </span>
          <span className="text-[11px] text-surface-500 font-mono block">{u.email}</span>
        </div>
      ),
    },
    {
      id: "roles",
      header: "Assigned Roles",
      accessor: (u) => (
        <div className="flex flex-wrap gap-1">
          {u.roles.map((r) => (
            <span
              key={r}
              className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-brand-50 text-brand-900 border border-brand-200"
            >
              {r}
            </span>
          ))}
        </div>
      ),
    },
    {
      id: "dept",
      header: "Department",
      width: "120px",
      accessor: (u) => <span className="text-xs text-surface-700">{u.department || "Enterprise"}</span>,
    },
    {
      id: "clearance",
      header: "Clearance Level",
      width: "140px",
      accessor: (u) => (
        <select
          value={u.clearance_level}
          onChange={(e) => handleChangeClearance(u, Number(e.target.value))}
          className="text-xs font-mono px-2 py-1 border border-surface-300 rounded bg-white font-semibold text-surface-800"
        >
          <option value={0}>0 (PUBLIC)</option>
          <option value={1}>1 (INTERNAL)</option>
          <option value={2}>2 (CONFIDENTIAL)</option>
          <option value={3}>3 (RESTRICTED)</option>
        </select>
      ),
    },
    {
      id: "status",
      header: "Status",
      width: "110px",
      accessor: (u) => (
        <StatusPill label={u.is_active ? "ACTIVE" : "SUSPENDED"} variant={u.is_active ? "success" : "danger"} />
      ),
    },
    {
      id: "actions",
      header: "Actions",
      width: "130px",
      accessor: (u) => (
        <Button
          variant={u.is_active ? "outline" : "primary"}
          size="sm"
          icon={u.is_active ? <UserX className="w-3 h-3 text-red-600" /> : <UserCheck className="w-3 h-3 text-emerald-600" />}
          onClick={() => handleToggleUserActive(u)}
        >
          {u.is_active ? "Suspend" : "Activate"}
        </Button>
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
        title="Administration & Governance Control"
        breadcrumbs={[{ label: "System" }, { label: "Tenant Administration" }]}
        badges={<StatusPill label="RBAC & SCIM 2.0 ENFORCED" variant="info" />}
        actions={
          <Button
            variant="outline"
            size="sm"
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
            onClick={loadData}
          >
            Refresh Telemetry
          </Button>
        }
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* KPI Cards */}
        {kpis && (
          <div className="grid grid-cols-6 gap-4">
            <div className="p-4 bg-white rounded-lg border border-surface-200 shadow-xs space-y-1">
              <span className="text-[11px] font-semibold text-surface-500 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-brand-600" /> Documents
              </span>
              <div className="text-xl font-bold text-surface-900">{kpis.total_documents}</div>
              <span className="text-[10px] text-surface-400 font-mono">{kpis.storage_mb_total} MB stored</span>
            </div>

            <div className="p-4 bg-white rounded-lg border border-surface-200 shadow-xs space-y-1">
              <span className="text-[11px] font-semibold text-surface-500 uppercase tracking-wider flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> Records
              </span>
              <div className="text-xl font-bold text-surface-900">{kpis.total_records}</div>
              <span className="text-[10px] text-emerald-700 font-medium">DoD 5015.02 locked</span>
            </div>

            <div className="p-4 bg-white rounded-lg border border-surface-200 shadow-xs space-y-1">
              <span className="text-[11px] font-semibold text-surface-500 uppercase tracking-wider flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-red-600" /> Legal Holds
              </span>
              <div className="text-xl font-bold text-red-700">{kpis.active_holds}</div>
              <span className="text-[10px] text-red-600 font-mono">{kpis.held_documents} assets frozen</span>
            </div>

            <div className="p-4 bg-white rounded-lg border border-surface-200 shadow-xs space-y-1">
              <span className="text-[11px] font-semibold text-surface-500 uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-600" /> Approvals
              </span>
              <div className="text-xl font-bold text-surface-900">{kpis.pending_tasks}</div>
              <span className="text-[10px] text-amber-700 font-medium">Pending action</span>
            </div>

            <div className="p-4 bg-white rounded-lg border border-surface-200 shadow-xs space-y-1">
              <span className="text-[11px] font-semibold text-surface-500 uppercase tracking-wider flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-purple-600" /> Active Users
              </span>
              <div className="text-xl font-bold text-surface-900">{kpis.active_users}</div>
              <span className="text-[10px] text-surface-400 font-mono">{kpis.total_users} provisioned</span>
            </div>

            <div className="p-4 bg-white rounded-lg border border-surface-200 shadow-xs space-y-1">
              <span className="text-[11px] font-semibold text-surface-500 uppercase tracking-wider flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-brand-600" /> Audit Ledger
              </span>
              <div className="text-xl font-bold text-surface-900">{kpis.audit_events_24h}</div>
              <span className="text-[10px] text-emerald-700 font-semibold">Chain sealed</span>
            </div>
          </div>
        )}

        {/* Infrastructure & Microservices Health */}
        {health && (
          <div className="p-5 bg-white rounded-lg border border-surface-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-surface-100 pb-3">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-brand-700" />
                <h3 className="text-xs font-bold text-surface-900 uppercase tracking-wider">
                  Enterprise Infrastructure Subsystems
                </h3>
              </div>
              <StatusPill
                label={`OVERALL: ${health.overall_status.toUpperCase()}`}
                variant={health.overall_status === "healthy" ? "success" : "warning"}
              />
            </div>

            <div className="grid grid-cols-5 gap-3">
              {Object.entries(health.services).map(([svcName, svc]) => (
                <div key={svcName} className="p-3 rounded-lg bg-surface-50 border border-surface-200 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-surface-900 uppercase">{svcName}</span>
                    <span
                      className={`w-2 h-2 rounded-full ${
                        svc.status === "healthy" ? "bg-emerald-500" : "bg-red-500"
                      }`}
                    />
                  </div>
                  <div className="text-[11px] font-semibold text-surface-600 capitalize">{svc.status}</div>
                  {svc.error && <p className="text-[10px] text-red-600 truncate">{svc.error}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* User Directory & SCIM Provisioning */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-surface-900 uppercase tracking-wider flex items-center gap-2">
              <Users className="w-4 h-4 text-brand-700" /> Enterprise User Directory & Clearance Controls
            </h3>
            <span className="text-xs text-surface-500">Live synchronization with SCIM 2.0 directory</span>
          </div>

          <div className="bg-white rounded-lg border border-surface-200 shadow-xs overflow-hidden">
            <DataTable
              columns={columns}
              data={users}
              keyExtractor={(u) => u.id}
              isLoading={isLoading}
              emptyMessage="No enterprise users found in this tenant."
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminView;
