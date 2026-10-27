import React from "react";
import { RadioTower, ArrowRight } from "lucide-react";
import { Button } from "./Button";
import { StatusPill } from "./StatusPill";

export interface NotConnectedStateProps {
  moduleName: string;
  description?: string;
  expectedEndpoint?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const NotConnectedState: React.FC<NotConnectedStateProps> = ({
  moduleName,
  description = "No fake mock data is displayed. Real records and telemetry will be populated once the backend endpoint is wired.",
  expectedEndpoint,
  actionLabel,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-surface-200 dark:border-surface-800 rounded-lg bg-surface-50/50 dark:bg-surface-900/50 max-w-2xl mx-auto my-8">
      <div className="p-3 bg-brand-50 dark:bg-brand-950/40 rounded-full mb-4">
        <RadioTower className="w-8 h-8 text-brand-600 dark:text-brand-400 stroke-[1.5]" />
      </div>

      <div className="mb-2">
        <StatusPill label="LIVE API NOT YET CONNECTED" variant="warning" />
      </div>

      <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100 mt-2">
        {moduleName} &mdash; Pending Live Backend
      </h3>

      <p className="text-xs text-surface-600 dark:text-surface-400 max-w-md mt-2 mb-4 leading-relaxed">
        {description}
      </p>

      {expectedEndpoint && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded text-[11px] font-mono text-surface-600 dark:text-surface-300 mb-6">
          <span className="font-semibold text-brand-600">TARGET:</span>
          <span>{expectedEndpoint}</span>
        </div>
      )}

      {actionLabel && onAction && (
        <Button variant="secondary" size="sm" onClick={onAction} icon={<ArrowRight className="w-3.5 h-3.5" />}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
};
