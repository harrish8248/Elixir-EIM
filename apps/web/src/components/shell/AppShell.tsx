import React, { useState, useEffect } from "react";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { Footer } from "./Footer";
import { ContentExplorerView } from "@/modules/content/ContentExplorerView";
import { RecordsPlanView } from "@/modules/records/RecordsPlanView";
import { TrustDashboardView } from "@/modules/governance/TrustDashboardView";
import { WorkflowView } from "@/modules/workflow/WorkflowView";
import { SearchView } from "@/modules/search/SearchView";
import { AdminView } from "@/modules/admin/AdminView";

import { useAuth } from "@/config/AuthContext";
import { ForbiddenView } from "@/components/auth/ForbiddenView";

function getPathFromHash(): string {
  const hash = window.location.hash.replace(/^#/, "");
  return hash.startsWith("/") ? hash : "/content";
}

export const AppShell: React.FC = () => {
  const { user, logout, isForbidden } = useAuth();
  const [currentPath, setCurrentPath] = useState<string>(() => getPathFromHash());
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [tenantName, setTenantName] = useState("AcroCorp Global (US-East)");
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    const handleHashChange = () => {
      const path = getPathFromHash();
      setCurrentPath(path);
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleNavigate = (path: string) => {
    window.location.hash = path;
    setCurrentPath(path);
  };

  const toggleDarkMode = () => {
    const nextMode = !isDarkMode;
    setIsDarkMode(nextMode);
    if (nextMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  const userDisplayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.username ||
    "Sarah Chen";
  const userPrimaryRole = user?.roles?.[0] || "RecordsManager";

  const renderCurrentView = () => {
    if (isForbidden || currentPath === "/forbidden") {
      return (
        <ForbiddenView
          reason="Policy Decision Point (PDP) rejected this request: insufficient permissions or clearance level."
          onGoBack={() => handleNavigate("/content")}
        />
      );
    }

    switch (currentPath) {
      case "/records":
        return <RecordsPlanView />;
      case "/workflow":
        return <WorkflowView />;
      case "/search":
        return <SearchView />;
      case "/governance":
      case "/audit":
        return <TrustDashboardView />;
      case "/admin":
        return <AdminView />;
      case "/content":
      default:
        return <ContentExplorerView />;
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100">
      {/* Top Navigation Bar */}
      <TopBar
        currentTenant={tenantName}
        onTenantChange={setTenantName}
        onSearchClick={() => handleNavigate("/search")}
        userRole={userPrimaryRole}
        userName={userDisplayName}
        isDarkMode={isDarkMode}
        onToggleDarkMode={toggleDarkMode}
        onLogout={logout}
      />

      {/* Main Workspace Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Module Sidebar */}
        <Sidebar
          currentPath={currentPath}
          onNavigate={handleNavigate}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />

        {/* Dynamic Center Work Area */}
        <main className="flex-1 flex flex-col overflow-hidden bg-surface-50 dark:bg-surface-900">
          {renderCurrentView()}
        </main>
      </div>

      {/* Enterprise Status & Version Footer */}
      <Footer />
    </div>
  );
};

export default AppShell;
