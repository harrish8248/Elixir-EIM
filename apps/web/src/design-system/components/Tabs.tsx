import React from "react";
import * as RadixTabs from "@radix-ui/react-tabs";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  content: React.ReactNode;
  badge?: string | number;
}

export interface TabsProps {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  items,
  defaultValue,
  value,
  onValueChange,
  className,
}) => {
  const initialValue = value !== undefined ? value : (defaultValue || items[0]?.id);

  return (
    <RadixTabs.Root
      value={value}
      defaultValue={defaultValue || initialValue}
      onValueChange={onValueChange}
      className={twMerge("flex flex-col w-full", className)}
    >
      <RadixTabs.List className="flex items-center gap-1 border-b border-surface-200 px-2 bg-surface-50">
        {items.map((tab) => (
          <RadixTabs.Trigger
            key={tab.id}
            value={tab.id}
            className={clsx(
              "flex items-center gap-2 px-3 py-2 text-xs font-medium border-b-2 transition-all select-none focus-visible:outline-none",
              "text-surface-600 hover:text-surface-900 border-transparent",
              "data-[state=active]:text-brand-900 data-[state=active]:border-brand-900 data-[state=active]:font-semibold"
            )}
          >
            {tab.icon && <span className="w-4 h-4 shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-surface-200 text-surface-700">
                {tab.badge}
              </span>
            )}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>

      {items.map((tab) => (
        <RadixTabs.Content
          key={tab.id}
          value={tab.id}
          className="pt-4 focus-visible:outline-none"
        >
          {tab.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
};
