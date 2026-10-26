import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  icon?: React.ReactNode;
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", icon, isLoading, children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 disabled:opacity-50 disabled:pointer-events-none text-sm select-none";

    const variantStyles = {
      primary: "bg-brand-900 text-white hover:bg-brand-800 active:bg-brand-950 border border-brand-900 shadow-sm",
      secondary: "bg-surface-100 text-surface-800 hover:bg-surface-200 border border-surface-300 shadow-sm",
      danger: "bg-status-danger text-white hover:bg-red-700 active:bg-red-800 border border-red-700 shadow-sm",
      ghost: "text-surface-700 hover:bg-surface-100 hover:text-surface-900",
      outline: "border border-surface-300 bg-transparent text-surface-800 hover:bg-surface-100",
    };

    const sizeStyles = {
      sm: "h-7 px-2.5 text-xs gap-1.5",
      md: "h-8.5 px-3 text-sm gap-2",
      lg: "h-10 px-4 text-base gap-2.5",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={twMerge(clsx(baseStyles, variantStyles[variant], sizeStyles[size], className))}
        {...props}
      >
        {isLoading ? (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin mr-1.5" />
        ) : icon ? (
          <span className="shrink-0">{icon}</span>
        ) : null}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
