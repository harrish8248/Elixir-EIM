import React from "react";
import { Search, Filter } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { NotConnectedState } from "@/design-system/components/NotConnectedState";

export const SearchView: React.FC = () => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title="Enterprise Search & Discovery"
        breadcrumbs={[{ label: "Discovery" }, { label: "Unified Search" }]}
        badges={<StatusPill label="INDEX: DISCONNECTED" variant="neutral" />}
        actions={
          <Button variant="secondary" size="sm" icon={<Filter className="w-3.5 h-3.5" />} disabled>
            Advanced Facets
          </Button>
        }
      />

      <div className="p-6 pb-2">
        <div className="relative max-w-2xl">
          <Search className="w-4 h-4 text-surface-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            disabled
            placeholder="Search across documents, legal holds, audit events, and metadata..."
            className="w-full pl-9 pr-4 py-2 text-xs bg-white border border-surface-300 rounded-md shadow-sm opacity-60 cursor-not-allowed"
          />
        </div>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        <NotConnectedState
          moduleName="Search & Discovery Index"
          description="Full-text tsvector searching, metadata faceted navigation, and OCR content queries will activate once the search service is wired to the API."
          expectedEndpoint="POST /api/v1/search/query"
        />
      </div>
    </div>
  );
};
