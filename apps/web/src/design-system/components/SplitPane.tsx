import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  leftWidth?: string;
  className?: string;
}

export const SplitPane: React.FC<SplitPaneProps> = ({
  left,
  right,
  leftWidth = "w-64",
  className,
}) => {
  return (
    <div className={twMerge("flex h-full w-full overflow-hidden border border-surface-200 rounded bg-white shadow-sm", className)}>
      <div
        className={clsx(
          "shrink-0 border-r border-surface-200 overflow-y-auto bg-surface-50 p-2 select-none",
          leftWidth
        )}
      >
        {left}
      </div>
      <div className="flex-1 overflow-y-auto bg-white p-4">{right}</div>
    </div>
  );
};
