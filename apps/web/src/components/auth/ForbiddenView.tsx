import React from "react";
import { ShieldAlert, ArrowLeft, LogOut } from "lucide-react";
import { Button } from "@/design-system/components/Button";
import { useAuth } from "@/config/AuthContext";

export interface ForbiddenViewProps {
  reason?: string;
  requiredClearance?: number;
  onGoBack?: () => void;
}

export const ForbiddenView: React.FC<ForbiddenViewProps> = ({
  reason = "Policy Decision Point (PDP) rejected this request: insufficient permissions or clearance.",
  requiredClearance = 4,
  onGoBack,
}) => {
  const { user, logout, clearForbidden } = useAuth();

  const handleBack = () => {
    clearForbidden();
    if (onGoBack) {
      onGoBack();
    } else {
      window.location.hash = "/content";
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] p-8 text-center bg-surface-50">
      <div className="w-16 h-16 rounded-2xl bg-red-100 text-red-600 flex items-center justify-center mb-5 shadow-inner">
        <ShieldAlert className="w-9 h-9" />
      </div>

      <h1 className="text-2xl font-bold text-surface-900 tracking-tight">403 - Access Denied</h1>
      <p className="text-sm font-medium text-red-600 mt-1">Open Policy Agent (OPA) PEP Enforcement</p>

      <p className="text-xs text-surface-600 max-w-md mt-3 leading-relaxed">
        {reason}
      </p>

      <div className="mt-6 p-4 rounded-lg bg-surface-100 border border-surface-200 text-left max-w-md w-full text-xs space-y-1.5">
        <div className="flex justify-between">
          <span className="text-surface-500">Authenticated Actor:</span>
          <span className="font-semibold text-surface-800">{user?.email || "Unknown"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-500">Assigned Roles:</span>
          <span className="font-semibold text-surface-800">{user?.roles.join(", ") || "None"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-500">Your Security Clearance:</span>
          <span className="font-semibold text-surface-800">Level {user?.clearance_level ?? 1}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-500">Required Clearance:</span>
          <span className="font-semibold text-red-700">Level {requiredClearance} (Restricted)</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-500">Audit Status:</span>
          <span className="font-mono text-emerald-700">DENY Logged to SHA-256 Ledger</span>
        </div>
      </div>

      <div className="flex gap-3 mt-6">
        <Button
          variant="secondary"
          onClick={handleBack}
          icon={<ArrowLeft className="w-4 h-4" />}
        >
          Return to Permitted Workspace
        </Button>
        <Button
          variant="outline"
          onClick={logout}
          icon={<LogOut className="w-4 h-4" />}
        >
          Switch Account
        </Button>
      </div>
    </div>
  );
};
