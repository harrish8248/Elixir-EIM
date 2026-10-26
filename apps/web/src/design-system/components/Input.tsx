import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, leftIcon, rightIcon, id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="flex flex-col gap-1 w-full text-left">
        {label && (
          <label htmlFor={inputId} className="text-xs font-semibold text-surface-700 select-none">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <span className="absolute left-2.5 text-surface-400 pointer-events-none shrink-0">
              {leftIcon}
            </span>
          )}
          <input
            id={inputId}
            ref={ref}
            className={twMerge(
              clsx(
                "h-8.5 w-full rounded border border-surface-300 bg-white px-3 text-sm text-surface-900 placeholder:text-surface-400 focus:border-brand-600 focus:outline-none focus:ring-1 focus:ring-brand-600 transition-colors disabled:bg-surface-100 disabled:text-surface-400",
                leftIcon && "pl-8",
                rightIcon && "pr-8",
                error && "border-status-danger focus:border-status-danger focus:ring-status-danger",
                className
              )
            )}
            {...props}
          />
          {rightIcon && (
            <span className="absolute right-2.5 text-surface-400 pointer-events-none shrink-0">
              {rightIcon}
            </span>
          )}
        </div>
        {error && <span className="text-xs text-status-danger mt-0.5">{error}</span>}
      </div>
    );
  }
);

Input.displayName = "Input";
