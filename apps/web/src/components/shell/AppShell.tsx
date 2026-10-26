import React, { useState } from "react";
import { TopBar } from "./TopBar";
import { Sidebar } from "./Sidebar";
import { Footer } from "./Footer";
import { ContentExplorerView } from "@/modules/content/ContentExplorerView";
import { RecordsPlanView } from "@/modules/records/RecordsPlanView";
import { TrustDashboardView } from "@/modules/governance/TrustDashboardView";

export const AppShell: React.FC = () => {
  const [currentPath, setCurrentPath] = useState("/content");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [tenantName, setTenantName] = useState("AcroCorp Global (US-East)");

  const renderCurrentView = () => {
    switch (currentPath) {
      case "/records":
        return <RecordsPlanView />;
      case "/governance":
      case "/audit":
        return <TrustDashboardView />;
      case "/content":
      default:
        return <ContentExplorerView />;
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-surface-50 text-surface-900">
      {/* Top Navigation Bar */}
      <TopBar
        currentTenant={tenantName}
        onTenantChange={setTenantName}
        onSearchClick={() => setCurrentPath("/content")}
        userRole="RecordsManager"
        userName="Sarah Chen"
      />

      {/* Main Workspace Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Module Sidebar */}
        <Sidebar
          currentPath={currentPath}
          onNavigate={(path) => setCurrentPath(path)}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        />

        {/* Dynamic Center Work Area */}
        <main className="flex-1 flex flex-col overflow-hidden bg-surface-50">
          {renderCurrentView()}
        </main>
      </div>

      {/* Enterprise Status & Version Footer */}
      <Footer />
    </div>
  );
};
