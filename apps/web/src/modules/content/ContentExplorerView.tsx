import React, { useState } from "react";
import {
  Folder,
  FileText,
  Upload,
  FolderPlus,
  Download,
  Lock,
  History,
  FileCheck,
} from "lucide-react";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { SplitPane } from "@/design-system/components/SplitPane";
import { PageHeader } from "@/components/shell/PageHeader";

interface DocumentItem {
  id: string;
  name: string;
  version: string;
  contentType: string;
  status: "held" | "record" | "draft";
  statusLabel: string;
  modified: string;
  author: string;
  size: string;
  sha256: string;
}

export const ContentExplorerView: React.FC = () => {
  const [selectedFolder, setSelectedFolder] = useState("Contracts / Vendor MSA");
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>({
    id: "doc-01",
    name: "Master_Services_Agreement_AcroCorp_2026.pdf",
    version: "v2.1",
    contentType: "Master Services Agreement",
    status: "held",
    statusLabel: "RECORD: HELD",
    modified: "Today 14:22",
    author: "Sarah Chen",
    size: "2.4 MB",
    sha256: "7f2b901ac83910ee2a94f0b29841bbce8749a901e138a0928bbfa931084ea912",
  });

  const documents: DocumentItem[] = [
    {
      id: "doc-01",
      name: "Master_Services_Agreement_AcroCorp_2026.pdf",
      version: "v2.1",
      contentType: "Master Services Agreement",
      status: "held",
      statusLabel: "RECORD: HELD",
      modified: "Today 14:22",
      author: "Sarah Chen",
      size: "2.4 MB",
      sha256: "7f2b901ac83910ee2a94f0b29841bbce8749a901e138a0928bbfa931084ea912",
    },
    {
      id: "doc-02",
      name: "Procurement_SOW_CloudMigration_v1.docx",
      version: "v1.0",
      contentType: "Statement of Work",
      status: "draft",
      statusLabel: "UNOFFICIAL",
      modified: "Oct 24 11:05",
      author: "Michael Diaz",
      size: "840 KB",
      sha256: "3d1c4b7890aef912384a9238910ebf1938a90281930192840192830192830192",
    },
    {
      id: "doc-03",
      name: "Mutual_NDA_Standard_Template.pdf",
      version: "v3.0",
      contentType: "Non-Disclosure Agreement",
      status: "record",
      statusLabel: "RETENTION: 7Y",
      modified: "Oct 19 08:30",
      author: "Kavita Patel",
      size: "1.1 MB",
      sha256: "9102839102840192830192830192830192830192830192830192830192830192",
    },
  ];

  const columns: Column<DocumentItem>[] = [
    {
      id: "name",
      header: "Name",
      accessor: (doc) => (
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-600 shrink-0" />
          <span className="font-medium text-surface-900 truncate max-w-xs">{doc.name}</span>
        </div>
      ),
    },
    {
      id: "version",
      header: "Version",
      width: "80px",
      accessor: (doc) => (
        <span className="font-mono text-xs text-surface-600">{doc.version}</span>
      ),
    },
    {
      id: "contentType",
      header: "Content Type",
      accessor: (doc) => <span className="text-surface-700">{doc.contentType}</span>,
    },
    {
      id: "status",
      header: "Records Status",
      accessor: (doc) => (
        <StatusPill
          label={doc.statusLabel}
          variant={doc.status === "held" ? "hold" : doc.status === "record" ? "record" : "neutral"}
        />
      ),
    },
    {
      id: "modified",
      header: "Modified",
      accessor: (doc) => <span className="text-surface-500 text-xs">{doc.modified}</span>,
    },
    {
      id: "author",
      header: "Author",
      accessor: (doc) => <span className="text-surface-700 text-xs">{doc.author}</span>,
    },
  ];

  const folderTree = (
    <div className="space-y-1 text-xs">
      <div className="font-semibold text-surface-400 uppercase tracking-wider px-2 py-1 select-none">
        Repository Workspaces
      </div>
      <div className="space-y-0.5">
        <button
          onClick={() => setSelectedFolder("Global Operations / Contracts")}
          className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-100 text-surface-700 font-medium text-left"
        >
          <Folder className="w-3.5 h-3.5 text-amber-500" /> Global Operations
        </button>
        <div className="pl-4 space-y-0.5">
          <button
            onClick={() => setSelectedFolder("Contracts / Vendor MSA")}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded bg-brand-50 text-brand-900 font-semibold text-left"
          >
            <Folder className="w-3.5 h-3.5 text-amber-600" /> Contracts & MSAs
          </button>
          <button
            onClick={() => setSelectedFolder("Human Resources / Policies")}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-100 text-surface-600 text-left"
          >
            <Folder className="w-3.5 h-3.5 text-amber-500" /> HR & Personnel
          </button>
          <button
            onClick={() => setSelectedFolder("Finance & Treasury / Audits")}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-surface-100 text-surface-600 text-left"
          >
            <Folder className="w-3.5 h-3.5 text-amber-500" /> Treasury & Audits
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      <PageHeader
        title={selectedFolder}
        breadcrumbs={[
          { label: "Workspaces" },
          { label: "Global Operations" },
          { label: "Contracts & MSAs" },
        ]}
        badges={
          <StatusPill label="CLASSIFICATION: CONFIDENTIAL" variant="warning" />
        }
        actions={
          <>
            <Button variant="secondary" size="sm" icon={<FolderPlus className="w-3.5 h-3.5" />}>
              New Folder
            </Button>
            <Button variant="primary" size="sm" icon={<Upload className="w-3.5 h-3.5" />}>
              Upload Document
            </Button>
          </>
        }
      />

      <div className="flex-1 p-4 overflow-hidden">
        <SplitPane
          left={folderTree}
          leftWidth="w-60"
          right={
            <div className="flex flex-col h-full gap-4 overflow-hidden">
              {/* Document List Table */}
              <div className="flex-1 overflow-auto">
                <DataTable
                  columns={columns}
                  data={documents}
                  keyExtractor={(doc) => doc.id}
                  selectedId={selectedDoc?.id}
                  onRowClick={(doc) => setSelectedDoc(doc)}
                />
              </div>

              {/* Document Inspection & Trust Drawer */}
              {selectedDoc && (
                <div className="border border-surface-200 rounded-lg p-4 bg-surface-50 shadow-sm shrink-0">
                  <div className="flex items-center justify-between pb-3 border-b border-surface-200">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-brand-600" />
                      <div>
                        <h3 className="text-sm font-bold text-surface-900">{selectedDoc.name}</h3>
                        <div className="flex items-center gap-2 text-xs text-surface-500 font-mono mt-0.5">
                          <span>Doc ID: {selectedDoc.id}</span>
                          <span>•</span>
                          <span>{selectedDoc.size}</span>
                          <span>•</span>
                          <span className="flex items-center gap-1 text-emerald-700">
                            <FileCheck className="w-3 h-3 text-emerald-600" /> ClamAV Clean
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" icon={<History className="w-3.5 h-3.5" />}>
                        Versions ({selectedDoc.version})
                      </Button>
                      <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>
                        Download
                      </Button>
                      <Button variant="danger" size="sm" icon={<Lock className="w-3.5 h-3.5" />}>
                        Manage Holds
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 pt-3 text-xs">
                    <div>
                      <span className="text-surface-500 font-semibold block">Retention Rule</span>
                      <span className="text-surface-800 font-medium mt-0.5 block">
                        Schedule SEC-07 (7 Years Post-Expiration)
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-500 font-semibold block">Litigation Hold</span>
                      <span className="text-red-700 font-semibold mt-0.5 block">
                        Active: Hold #891 (DOJ Civil Inquiry)
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-500 font-semibold block">Cryptographic Seal</span>
                      <span className="font-mono text-[11px] text-surface-600 truncate mt-0.5 block">
                        {selectedDoc.sha256.substring(0, 24)}... (Verified)
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          }
        />
      </div>
    </div>
  );
};
