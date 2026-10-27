import React from "react";
import { useAuth } from "@/config/AuthContext";

export interface PermissionGateProps {
  requiredPermission?: string;
  requiredRole?: string;
  minClearance?: number;
  userPermissions?: string[];
  userRoles?: string[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  requiredPermission,
  requiredRole,
  minClearance,
  userPermissions,
  userRoles,
  fallback = null,
  children,
}) => {
  let contextRoles: string[] = [];
  let clearance = 1;

  try {
    const auth = useAuth();
    if (auth.user) {
      contextRoles = auth.user.roles || [];
      clearance = auth.user.clearance_level || 1;
    }
  } catch {
    // Fallback if rendered outside AuthProvider
  }

  const effectiveRoles = userRoles || contextRoles;
  const isGlobalAdmin = effectiveRoles.includes("GlobalAdmin");

  const hasRole = !requiredRole || effectiveRoles.includes(requiredRole) || isGlobalAdmin;
  const hasClearance = !minClearance || clearance >= minClearance || isGlobalAdmin;
  const hasPerm =
    !requiredPermission ||
    (userPermissions && userPermissions.includes(requiredPermission)) ||
    isGlobalAdmin;

  if (!hasRole || !hasPerm || !hasClearance) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};
