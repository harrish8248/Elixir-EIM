import { Search, Bell, HelpCircle, Building2, Shield, User, Sun, Moon } from "lucide-react";
import { BRANDING } from "@/config/branding";

export interface TopBarProps {
  currentTenant: string;
  onTenantChange?: (tenant: string) => void;
  onSearchClick?: () => void;
  userRole?: string;
  userName?: string;
  isDarkMode?: boolean;
  onToggleDarkMode?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  currentTenant,
  onTenantChange,
  onSearchClick,
  userRole = "RecordsManager",
  userName = "Sarah Chen",
  isDarkMode = false,
  onToggleDarkMode,
}) => {
  return (
    <header className="h-12 bg-brand-950 text-white flex items-center justify-between px-4 border-b border-surface-800 select-none shrink-0 z-30">
      {/* Brand & Suite Name */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-brand-600 flex items-center justify-center font-bold text-xs tracking-wider shadow">
            E
          </div>
          <span className="font-semibold text-sm tracking-tight text-slate-100">
            {BRANDING.shortName}
          </span>
        </div>
        <span className="text-xs px-1.5 py-0.5 rounded bg-surface-800 text-surface-400 font-mono">
          v{BRANDING.version}
        </span>
      </div>

      {/* Global Search Bar (Ctrl+K) */}
      <div className="flex-1 max-w-md mx-6">
        <button
          onClick={onSearchClick}
          className="w-full h-7.5 bg-surface-900 border border-surface-700 hover:border-surface-600 rounded px-3 flex items-center justify-between text-xs text-surface-400 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-surface-400" />
            <span>Search documents, records, workflows...</span>
          </div>
          <kbd className="bg-surface-800 text-surface-400 px-1.5 py-0.5 rounded text-[10px] font-mono border border-surface-700">
            Ctrl+K
          </kbd>
        </button>
      </div>

      {/* Tenant Switcher & User Profile */}
      <div className="flex items-center gap-4">
        {/* Tenant Switcher */}
        <button
          onClick={() => onTenantChange?.("AcroCorp EMEA")}
          className="flex items-center gap-1.5 bg-surface-900 px-2.5 py-1 rounded border border-surface-700 text-xs text-slate-200 cursor-pointer hover:bg-surface-800 transition-colors"
        >
          <Building2 className="w-3.5 h-3.5 text-brand-400" />
          <span className="font-medium">{currentTenant}</span>
        </button>

        {/* Theme Toggle, Notifications & Help */}
        <div className="flex items-center gap-1 text-surface-400">
          <button
            onClick={onToggleDarkMode}
            title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
            className="p-1 hover:text-white rounded hover:bg-surface-800 transition-colors"
          >
            {isDarkMode ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-300" />}
          </button>
          <button
            title="Notifications"
            className="p-1 hover:text-white rounded hover:bg-surface-800 transition-colors relative"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-brand-500 rounded-full" />
          </button>
          <button
            title="Help & Documentation"
            className="p-1 hover:text-white rounded hover:bg-surface-800 transition-colors"
          >
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>

        <div className="h-4 w-px bg-surface-800" />

        {/* User Badge */}
        <div className="flex items-center gap-2 text-xs">
          <div className="w-6 h-6 rounded-full bg-surface-700 flex items-center justify-center text-slate-200">
            <User className="w-3.5 h-3.5" />
          </div>
          <div className="flex flex-col text-left leading-tight">
            <span className="font-medium text-slate-200">{userName}</span>
            <span className="text-[10px] text-surface-400 font-mono flex items-center gap-1">
              <Shield className="w-2.5 h-2.5 text-emerald-400" /> {userRole}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
