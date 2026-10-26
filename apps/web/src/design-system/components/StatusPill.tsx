import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export type StatusVariant =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "hold"
  | "record";

export interface StatusPillProps {
  label: string;
  variant?: StatusVariant;
  icon?: React.ReactNode;
  className?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({
  label,
  variant = "neutral",
  icon,
  className,
}) => {
  const variantStyles: Record<StatusVariant, string> = {
    neutral: "bg-surface-100 text-surface-700 border-surface-300",
    success: "bg-emerald-50 text-emerald-700 border-emerald-300",
    warning: "bg-amber-50 text-amber-700 border-amber-300",
    danger: "bg-red-50 text-red-700 border-red-300",
    info: "bg-sky-50 text-sky-700 border-sky-300",
    hold: "bg-red-100 text-red-800 border-red-400 font-semibold tracking-wide",
    record: "bg-slate-900 text-slate-100 border-slate-950 font-medium",
  };

  return (
    <span
      className={twMerge(
        clsx(
          "inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border font-mono tracking-tight shrink-0 select-none",
          variantStyles[variant],
          className
        )
      )}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {label}
    </span>
  );
};
