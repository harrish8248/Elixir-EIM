import React from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface ToastProps {
  id?: string;
  type?: "success" | "error" | "warning" | "info";
  title: string;
  message?: string;
  onClose?: () => void;
  className?: string;
}

export const Toast: React.FC<ToastProps> = ({
  type = "info",
  title,
  message,
  onClose,
  className,
}) => {
  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />,
    error: <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />,
    info: <Info className="w-5 h-5 text-brand-600 shrink-0" />,
  };

  const borders = {
    success: "border-emerald-200 bg-emerald-50/80",
    error: "border-red-200 bg-red-50/80",
    warning: "border-amber-200 bg-amber-50/80",
    info: "border-brand-200 bg-brand-50/80",
  };

  return (
    <div
      role="status"
      className={twMerge(
        clsx(
          "flex items-start gap-3 p-3.5 rounded-lg border shadow-md max-w-sm w-full transition-all bg-surface-50",
          borders[type],
          className
        )
      )}
    >
      {icons[type]}
      <div className="flex-1 min-w-0">
        <h4 className="text-xs font-semibold text-surface-900">{title}</h4>
        {message && <p className="text-xs text-surface-600 mt-0.5 leading-normal">{message}</p>}
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="text-surface-400 hover:text-surface-700 p-0.5 rounded transition-colors"
          aria-label="Dismiss notification"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
