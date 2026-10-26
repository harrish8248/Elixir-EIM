import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ArrowUpDown } from "lucide-react";

export interface Column<T> {
  id: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  width?: string;
  sortable?: boolean;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  selectedId?: string;
  onRowClick?: (row: T) => void;
  isLoading?: boolean;
  emptyMessage?: string;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  selectedId,
  onRowClick,
  isLoading,
  emptyMessage = "No records found.",
  className,
}: DataTableProps<T>) {
  return (
    <div className={twMerge("w-full border border-surface-200 rounded overflow-hidden bg-white shadow-sm", className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead className="bg-surface-100 border-b border-surface-200 sticky top-0 z-10 select-none">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.id}
                  style={{ width: col.width }}
                  className="h-9 px-3 text-xs font-semibold text-surface-700 tracking-tight whitespace-nowrap"
                >
                  <div className="flex items-center gap-1.5">
                    {col.header}
                    {col.sortable && <ArrowUpDown className="w-3 h-3 text-surface-400" />}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-200">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {columns.map((col) => (
                    <td key={col.id} className="h-9 px-3">
                      <div className="h-4 bg-surface-200 rounded w-3/4" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="h-24 text-center text-sm text-surface-500 italic"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row) => {
                const id = keyExtractor(row);
                const isSelected = selectedId === id;
                return (
                  <tr
                    key={id}
                    onClick={() => onRowClick?.(row)}
                    className={clsx(
                      "h-9 transition-colors cursor-pointer select-none",
                      isSelected
                        ? "bg-brand-50 text-brand-900 font-medium"
                        : "hover:bg-surface-50 text-surface-800"
                    )}
                  >
                    {columns.map((col) => (
                      <td key={col.id} className="px-3 whitespace-nowrap">
                        {col.accessor(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
