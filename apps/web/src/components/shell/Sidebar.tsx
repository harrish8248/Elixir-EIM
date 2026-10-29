import React from "react";
import {
  FolderTree,
  ShieldAlert,
  GitBranch,
  Search,
  Sliders,
  FileCheck2,
  Settings,
  ChevronLeft,
  ChevronRight,
  ScanLine,
  Cpu,
} from "lucide-react";
import { clsx } from "clsx";

export interface NavItem {
  id: string;
  title: string;
  path: string;
  icon: React.ReactNode;
  badge?: string | number;
  badgeVariant?: "neutral" | "danger" | "brand";
}

export interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentPath,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
}) => {
  const primaryNavItems: NavItem[] = [
    {
      id: "content",
      title: "Content Services",
      path: "/content",
      icon: <FolderTree className="w-4 h-4 shrink-0" />,
    },
    {
      id: "idp",
      title: "Capture & IDP",
      path: "/idp",
      icon: <ScanLine className="w-4 h-4 shrink-0" />,
      badge: "STP 78%",
      badgeVariant: "brand",
    },
    {
      id: "ocr_engines",
      title: "OCR Engines",
      path: "/idp/engines",
      icon: <Cpu className="w-4 h-4 shrink-0" />,
      badge: "8 Ready",
      badgeVariant: "neutral",
    },
    {
      id: "records",
      title: "Records & Retention",
      path: "/records",
      icon: <ShieldAlert className="w-4 h-4 shrink-0" />,
    },
    {
      id: "workflow",
      title: "Process Automation",
      path: "/workflow",
      icon: <GitBranch className="w-4 h-4 shrink-0" />,
    },
    {
      id: "search",
      title: "Search & Discovery",
      path: "/search",
      icon: <Search className="w-4 h-4 shrink-0" />,
    },
  ];

  const governanceNavItems: NavItem[] = [
    {
      id: "governance",
      title: "Policy & Guardrails",
      path: "/governance",
      icon: <Sliders className="w-4 h-4 shrink-0" />,
    },
    {
      id: "audit",
      title: "Audit & Compliance",
      path: "/audit",
      icon: <FileCheck2 className="w-4 h-4 shrink-0" />,
    },
    {
      id: "admin",
      title: "Administration",
      path: "/admin",
      icon: <Settings className="w-4 h-4 shrink-0" />,
    },
  ];

  const renderNavGroup = (items: NavItem[], groupTitle?: string) => (
    <div className="space-y-0.5">
      {groupTitle && !isCollapsed && (
        <div className="px-3 pt-3 pb-1 text-[11px] font-semibold text-surface-400 uppercase tracking-wider select-none">
          {groupTitle}
        </div>
      )}
      {items.map((item) => {
        const isActive =
          currentPath === item.path ||
          (item.path !== "/idp" && currentPath.startsWith(item.path + "/")) ||
          (item.path === "/idp" && currentPath.startsWith("/idp/workbench"));
        return (
          <button
            key={item.id}
            onClick={() => onNavigate(item.path)}
            title={isCollapsed ? item.title : undefined}
            className={clsx(
              "w-full flex items-center gap-2.5 px-3 py-1.5 text-xs font-medium rounded transition-colors select-none text-left",
              isActive
                ? "bg-brand-50 text-brand-900 font-semibold"
                : "text-surface-600 hover:bg-surface-100 hover:text-surface-900"
            )}
          >
            <span className={isActive ? "text-brand-700" : "text-surface-500"}>
              {item.icon}
            </span>
            {!isCollapsed && (
              <>
                <span className="flex-1 truncate">{item.title}</span>
                {item.badge && (
                  <span
                    className={clsx(
                      "px-1.5 py-0.2 rounded text-[10px] font-mono",
                      item.badgeVariant === "danger"
                        ? "bg-red-100 text-red-700 font-semibold"
                        : item.badgeVariant === "brand"
                        ? "bg-brand-100 text-brand-800 font-semibold"
                        : "bg-surface-200 text-surface-600"
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </button>
        );
      })}
    </div>
  );

  return (
    <aside
      className={clsx(
        "bg-surface-50 border-r border-surface-200 flex flex-col justify-between shrink-0 transition-all duration-150 ease-in-out select-none",
        isCollapsed ? "w-14" : "w-56"
      )}
    >
      <div className="p-2 space-y-4 overflow-y-auto">
        {renderNavGroup(primaryNavItems)}
        <div className="h-px bg-surface-200 mx-2" />
        {renderNavGroup(governanceNavItems, "Governance & Trust")}
      </div>

      {/* Collapse Toggle Footer */}
      <div className="p-2 border-t border-surface-200 flex items-center justify-between text-surface-500">
        {!isCollapsed && (
          <span className="text-[11px] text-surface-400 pl-2">Elixir Trust Layer</span>
        )}
        <button
          onClick={onToggleCollapse}
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="p-1 hover:bg-surface-200 rounded text-surface-600 ml-auto"
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>
    </aside>
  );
};
