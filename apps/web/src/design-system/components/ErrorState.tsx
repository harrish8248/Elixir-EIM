import React, { useState } from "react";
import { AlertOctagon, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "./Button";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface ErrorStateProps {
  title?: string;
  message?: string;
  errorCode?: string;
  errorDetails?: string | Error;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "An Error Occurred",
  message = "Failed to load enterprise data from the API service.",
  errorCode,
  errorDetails,
  onRetry,
  className,
}) => {
  const [showDetails, setShowDetails] = useState(false);

  const detailText =
    typeof errorDetails === "string"
      ? errorDetails
      : errorDetails instanceof Error
      ? `${errorDetails.name}: ${errorDetails.message}\n${errorDetails.stack || ""}`
      : null;

  return (
    <div
      role="alert"
      className={twMerge(
        clsx(
          "flex flex-col items-center justify-center p-8 text-center rounded-lg border border-red-200 bg-red-50/50 max-w-lg mx-auto my-6",
          className
        )
      )}
    >
      <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mb-4">
        <AlertOctagon className="w-6 h-6" />
      </div>

      <h3 className="text-base font-semibold text-surface-900 mb-1">{title}</h3>
      <p className="text-xs text-surface-600 max-w-sm mb-4 leading-relaxed">{message}</p>

      {errorCode && (
        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono bg-red-100 text-red-800 mb-4">
          Code: {errorCode}
        </span>
      )}

      {onRetry && (
        <Button variant="secondary" size="sm" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={onRetry}>
          Try Again
        </Button>
      )}

      {detailText && (
        <div className="w-full mt-4 text-left">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-1 text-[11px] font-medium text-surface-500 hover:text-surface-700"
          >
            {showDetails ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            <span>{showDetails ? "Hide technical diagnostic details" : "Show technical diagnostic details"}</span>
          </button>

          {showDetails && (
            <pre className="mt-2 p-3 text-[11px] font-mono bg-surface-900 text-red-200 rounded overflow-x-auto whitespace-pre-wrap max-h-40">
              {detailText}
            </pre>
          )}
        </div>
      )}
    </div>
  );
};
