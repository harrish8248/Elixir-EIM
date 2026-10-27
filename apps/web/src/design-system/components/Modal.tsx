import React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: "sm" | "md" | "lg" | "xl";
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  maxWidth = "md",
}) => {
  const widthClasses = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
    xl: "max-w-xl",
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50 animate-fade-in" />
        <Dialog.Content
          className={twMerge(
            clsx(
              "fixed left-[50%] top-[50%] z-50 w-full translate-x-[-50%] translate-y-[-50%] rounded-lg bg-surface-50 p-6 shadow-xl border border-surface-200 focus:outline-none",
              widthClasses[maxWidth]
            )
          )}
        >
          <div className="flex items-center justify-between pb-3 border-b border-surface-200">
            <Dialog.Title className="text-base font-semibold text-surface-900">
              {title}
            </Dialog.Title>
            <Dialog.Close className="text-surface-400 hover:text-surface-700 transition-colors p-1 rounded hover:bg-surface-100">
              <X className="w-4 h-4" />
              <span className="sr-only">Close</span>
            </Dialog.Close>
          </div>

          {description && (
            <Dialog.Description className="text-xs text-surface-600 mt-2">
              {description}
            </Dialog.Description>
          )}

          <div className="py-4 text-sm text-surface-800">{children}</div>

          {footer && (
            <div className="flex justify-end gap-2 pt-3 border-t border-surface-200">
              {footer}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
