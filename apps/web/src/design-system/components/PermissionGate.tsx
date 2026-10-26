import React from "react";

export interface PermissionGateProps {
  requiredPermission?: string;
  requiredRole?: string;
  userPermissions?: string[];
  userRoles?: string[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  requiredPermission,
  requiredRole,
  userPermissions = [],
  userRoles = [],
  fallback = null,
  children,
}) => {
  const hasRole = !requiredRole || userRoles.includes(requiredRole) || userRoles.includes("GlobalAdmin");
  const hasPerm =
    !requiredPermission ||
    userPermissions.includes(requiredPermission) ||
    userRoles.includes("GlobalAdmin");

  if (!hasRole || !hasPerm) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};
