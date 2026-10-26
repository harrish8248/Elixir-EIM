import React from "react";
import { BRANDING } from "@/config/branding";
import { CheckCircle2 } from "lucide-react";

export const Footer: React.FC = () => {
  return (
    <footer className="h-6 bg-surface-100 border-t border-surface-200 px-3 flex items-center justify-between text-[11px] text-surface-500 font-mono select-none shrink-0">
      <div className="flex items-center gap-3">
        <span className="font-semibold text-surface-700">{BRANDING.shortName} v{BRANDING.version}</span>
        <span className="text-surface-300">|</span>
        <span className="flex items-center gap-1 text-emerald-700">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" /> All Systems Operational
        </span>
        <span className="text-surface-300">|</span>
        <span className="text-surface-400">Correlation ID: c89a-110e-821f</span>
      </div>

      <div className="text-surface-400">
        {BRANDING.copyright}
      </div>
    </footer>
  );
};
