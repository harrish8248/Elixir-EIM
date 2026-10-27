import React, { useState, useCallback } from "react";
import {
  Search,
  Filter,
  FileText,
  FileSearch,
  Sparkles,
} from "lucide-react";
import {
  apiClient,
  SearchResultItem,
  SearchResponse,
} from "@/api/client";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";

export const SearchView: React.FC = () => {
  const [query, setQuery] = useState("");
  const [selectedCls, setSelectedCls] = useState<string | undefined>(undefined);
  const [selectedDept, setSelectedDept] = useState<string | undefined>(undefined);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [facets, setFacets] = useState<{
    classifications: Record<string, number>;
    departments: Record<string, number>;
  }>({ classifications: {}, departments: {} });
  const [total, setTotal] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const executeSearch = useCallback(
    async (searchQuery: string, cls?: string, dept?: string) => {
      const q = searchQuery.trim();
      if (!q) {
        setResults([]);
        setTotal(null);
        setHasSearched(false);
        return;
      }

      try {
        setIsLoading(true);
        setHasSearched(true);
        const res: SearchResponse = await apiClient.search(q, {
          classification: cls,
          department: dept,
        });
        setResults(res.results || []);
        setTotal(res.total || 0);
        setFacets(res.facets || { classifications: {}, departments: {} });
      } catch (err) {
        console.error("Search error:", err);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(query, selectedCls, selectedDept);
  };

  const handleQuickChip = (term: string) => {
    setQuery(term);
    executeSearch(term, selectedCls, selectedDept);
  };

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Enterprise Search & Discovery"
        breadcrumbs={[{ label: "Discovery" }, { label: "Unified Search" }]}
        badges={<StatusPill label="POSTGRES FTS + ACL TRIMMING ACTIVE" variant="success" />}
      />

      {/* Search Input Hero Bar */}
      <div className="p-6 bg-white border-b border-surface-200 shadow-2xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex gap-2 max-w-3xl">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-surface-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search across documents, legal holds, audit events, metadata..."
              className="w-full pl-9 pr-4 py-2.5 text-xs bg-surface-50 border border-surface-300 rounded-lg shadow-inner focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white text-surface-900"
            />
          </div>
          <Button type="submit" variant="primary" size="md" disabled={!query.trim() || isLoading}>
            {isLoading ? "Searching..." : "Search"}
          </Button>
        </form>

        {/* Quick query chips */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-surface-400 flex items-center gap-1 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Popular queries:
          </span>
          {["Finance", "Policy", "Contracts", "DOJ", "Q3", "Vendor"].map((chip) => (
            <button
              key={chip}
              onClick={() => handleQuickChip(chip)}
              className="px-2 py-0.5 rounded-full bg-surface-100 hover:bg-surface-200 text-surface-700 text-[11px] font-medium transition-colors"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* Search Content & Facets */}
      <div className="flex-1 p-6 overflow-hidden flex gap-6">
        {/* Left Facets Sidebar */}
        <div className="w-64 bg-white rounded-lg border border-surface-200 p-4 shrink-0 space-y-5 h-fit shadow-xs">
          <div className="flex items-center justify-between pb-2 border-b border-surface-200">
            <span className="font-bold text-xs text-surface-900 flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-brand-600" /> Faceted Discovery
            </span>
            {(selectedCls || selectedDept) && (
              <button
                onClick={() => {
                  setSelectedCls(undefined);
                  setSelectedDept(undefined);
                  executeSearch(query, undefined, undefined);
                }}
                className="text-[11px] text-brand-700 hover:underline"
              >
                Clear
              </button>
            )}
          </div>

          {/* Classification Facet */}
          <div className="space-y-1 text-xs">
            <span className="font-semibold text-surface-500 uppercase tracking-wider text-[10px] block">
              Clearance Level
            </span>
            {["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"].map((cls) => {
              const count = facets.classifications[cls] || 0;
              const isSelected = selectedCls === cls;
              return (
                <button
                  key={cls}
                  onClick={() => {
                    const next = isSelected ? undefined : cls;
                    setSelectedCls(next);
                    executeSearch(query, next, selectedDept);
                  }}
                  className={`w-full flex items-center justify-between px-2 py-1.5 rounded transition-colors text-left ${
                    isSelected ? "bg-brand-50 text-brand-900 font-bold" : "hover:bg-surface-100 text-surface-700"
                  }`}
                >
                  <span>{cls}</span>
                  <span className="text-[10px] font-mono text-surface-400 bg-surface-100 px-1.5 py-0.2 rounded">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Department Facet */}
          <div className="space-y-1 text-xs pt-3 border-t border-surface-100">
            <span className="font-semibold text-surface-500 uppercase tracking-wider text-[10px] block">
              Department
            </span>
            {["Finance", "HR", "Legal", "Operations"].map((dept) => {
              const count = facets.departments[dept] || 0;
              const isSelected = selectedDept === dept;
              return (
                <button
                  key={dept}
                  onClick={() => {
                    const next = isSelected ? undefined : dept;
                    setSelectedDept(next);
                    executeSearch(query, selectedCls, next);
                  }}
                  className={`w-full flex items-center justify-between px-2 py-1.5 rounded transition-colors text-left ${
                    isSelected ? "bg-brand-50 text-brand-900 font-bold" : "hover:bg-surface-100 text-surface-700"
                  }`}
                >
                  <span>{dept}</span>
                  <span className="text-[10px] font-mono text-surface-400 bg-surface-100 px-1.5 py-0.2 rounded">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Search Results */}
        <div className="flex-1 overflow-y-auto space-y-3">
          {total !== null && (
            <div className="text-xs text-surface-500 font-medium">
              Found <span className="font-bold text-surface-900">{total}</span> documents matching "
              <span className="italic">{query}</span>" with ACL clearance verification applied.
            </div>
          )}

          {results.map((doc) => (
            <div
              key={doc.id}
              className="bg-white rounded-lg border border-surface-200 p-4 shadow-xs hover:border-brand-300 transition-colors space-y-2"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-brand-700 shrink-0" />
                  <h3 className="text-sm font-bold text-surface-900 hover:text-brand-900 cursor-pointer">
                    {doc.name}
                  </h3>
                  {doc.is_record && <StatusPill label="RECORD" variant="record" />}
                  {doc.status === "held" && <StatusPill label="LITIGATION HOLD" variant="hold" />}
                </div>
                <StatusPill
                  label={doc.classification}
                  variant={
                    doc.classification === "RESTRICTED"
                      ? "danger"
                      : doc.classification === "CONFIDENTIAL"
                      ? "warning"
                      : "neutral"
                  }
                />
              </div>

              {doc.description && <p className="text-xs text-surface-600 line-clamp-2">{doc.description}</p>}

              <div className="flex items-center gap-4 text-[11px] text-surface-400 pt-1 border-t border-surface-100 font-mono">
                <span>Dept: {doc.department || "Enterprise"}</span>
                <span>•</span>
                <span>Size: {formatBytes(doc.size_bytes)}</span>
                <span>•</span>
                <span>FTS Rank: {doc.rank.toFixed(3)}</span>
                <span>•</span>
                <span>Created: {new Date(doc.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}

          {!hasSearched && (
            <div className="bg-white rounded-lg border border-surface-200 p-12 text-center space-y-3 shadow-xs">
              <FileSearch className="w-10 h-10 text-brand-600 mx-auto" />
              <h3 className="text-sm font-bold text-surface-900">Unified PostgreSQL FTS Search Ready</h3>
              <p className="text-xs text-surface-500 max-w-md mx-auto">
                Type a keyword above (e.g. "Finance", "Policy", "Contract") to search across the enterprise repository
                with real-time Policy Decision Point (PDP) clearance filtering.
              </p>
            </div>
          )}

          {hasSearched && results.length === 0 && !isLoading && (
            <div className="bg-white rounded-lg border border-surface-200 p-12 text-center space-y-2 shadow-xs">
              <Search className="w-8 h-8 text-surface-300 mx-auto" />
              <h3 className="text-sm font-bold text-surface-900">No Documents Found</h3>
              <p className="text-xs text-surface-500 max-w-md mx-auto">
                No indexed files matched "{query}" for your security clearance level. Try refining your keywords or
                clearing the active filters.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SearchView;
