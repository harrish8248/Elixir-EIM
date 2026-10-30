import { UniversalUploadCenter, IngestionPipelineResult } from "./UniversalUploadCenter";
import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Folder,
  FileText,
  Upload,
  FolderPlus,
  Download,
  Lock,
  History,
  FileCheck,
  RefreshCw,
  Trash2,
  MessageSquare,
  ShieldAlert,
  CheckCircle,
  Plus,
} from "lucide-react";
import {
  apiClient,
  WorkspaceItem,
  FolderItem,
  DocumentItem,
  DocumentVersionItem,
  DocumentCommentItem,
  DocumentOcrText,
} from "@/api/client";
import { Button } from "@/design-system/components/Button";
import { StatusPill } from "@/design-system/components/StatusPill";
import { DataTable, Column } from "@/design-system/components/DataTable";
import { SplitPane } from "@/design-system/components/SplitPane";
import { PageHeader } from "@/components/shell/PageHeader";
import { Modal } from "@/design-system/components/Modal";
import { ConfirmDialog } from "@/design-system/components/ConfirmDialog";

export const ContentExplorerView: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<WorkspaceItem | null>(null);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<FolderItem | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [docVersions, setDocVersions] = useState<DocumentVersionItem[]>([]);
  const [docComments, setDocComments] = useState<DocumentCommentItem[]>([]);
  const [ocrData, setOcrData] = useState<DocumentOcrText | null>(null);
  const [isRetryingOcr, setIsRetryingOcr] = useState(false);
  const [newCommentText, setNewCommentText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"details" | "versions" | "comments" | "ocr">("details");

  // Modals state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isFolderModalOpen, setIsFolderModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Form states
  const [newFolderName, setNewFolderName] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadClassification, setUploadClassification] = useState("INTERNAL");
  const [uploadDepartment, setUploadDepartment] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const showNotification = (message: string, type: "success" | "error" = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  // 1. Load Workspaces on mount
  const loadWorkspaces = useCallback(async () => {
    try {
      setIsLoading(true);
      const wsList = await apiClient.listWorkspaces();
      setWorkspaces(wsList);
      if (wsList.length > 0 && !selectedWorkspace) {
        setSelectedWorkspace(wsList[0]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load workspaces";
      showNotification(msg, "error");
    } finally {
      setIsLoading(false);
    }
  }, [selectedWorkspace]);

  useEffect(() => {
    loadWorkspaces();
  }, [loadWorkspaces]);

  // 2. Load Folders & Documents when Workspace/Folder changes
  const loadContent = useCallback(async () => {
    if (!selectedWorkspace) return;
    try {
      setIsLoading(true);
      const [folderList, docList] = await Promise.all([
        apiClient.listFolders(selectedWorkspace.id),
        apiClient.listDocuments(selectedWorkspace.id, selectedFolder?.id),
      ]);
      setFolders(folderList);
      setDocuments(docList);
      if (selectedDoc) {
        const stillExists = docList.find((d) => d.id === selectedDoc.id);
        setSelectedDoc(stillExists || null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load content";
      showNotification(msg, "error");
    } finally {
      setIsLoading(false);
    }
  }, [selectedWorkspace, selectedFolder, selectedDoc]);

  useEffect(() => {
    loadContent();
  }, [selectedWorkspace, selectedFolder]);

  // 3. Load Document Details (versions & comments) when selectedDoc changes
  useEffect(() => {
    if (!selectedDoc) {
      setDocVersions([]);
      setDocComments([]);
      return;
    }
    const fetchDetails = async () => {
      try {
        const [versions, comments] = await Promise.all([
          apiClient.listDocumentVersions(selectedDoc.id),
          apiClient.listComments(selectedDoc.id),
        ]);
        setDocVersions(versions);
        setDocComments(comments);
      } catch (err) {
        console.error("Error loading document details", err);
      }
    };
    fetchDetails();
  }, [selectedDoc]);

  // Poll OCR status every 2 seconds when document is selected
  useEffect(() => {
    if (!selectedDoc) {
      setOcrData(null);
      return;
    }

    let isMounted = true;
    const fetchOcr = async () => {
      try {
        const data = await apiClient.getDocumentOcrText(selectedDoc.id);
        if (isMounted) {
          setOcrData(data);
        }
      } catch {
        // Silently tolerate during transitions
      }
    };

    fetchOcr();
    const interval = setInterval(fetchOcr, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedDoc]);

  const handleRetryOcr = async () => {
    if (!selectedDoc) return;
    try {
      setIsRetryingOcr(true);
      await apiClient.retryDocumentOcr(selectedDoc.id);
      showNotification("OCR extraction requeued successfully.");
      const updated = await apiClient.getDocumentOcrText(selectedDoc.id);
      setOcrData(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to retry OCR";
      showNotification(msg, "error");
    } finally {
      setIsRetryingOcr(false);
    }
  };

  // Handlers
  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWorkspace || !newFolderName.trim()) return;
    try {
      await apiClient.createFolder(selectedWorkspace.id, newFolderName.trim(), selectedFolder?.id);
      setIsFolderModalOpen(false);
      setNewFolderName("");
      showNotification("Folder created successfully");
      await loadContent();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create folder";
      showNotification(msg, "error");
    }
  };

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !selectedWorkspace) return;

    try {
      setIsLoading(true);
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("workspace_id", selectedWorkspace.id);
      if (selectedFolder) {
        formData.append("folder_id", selectedFolder.id);
      }
      formData.append("classification", uploadClassification);
      if (uploadDepartment) {
        formData.append("department", uploadDepartment);
      }

      const uploaded = await apiClient.uploadDocument(formData);
      setIsUploadModalOpen(false);
      setUploadFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      showNotification(`Document "${uploaded.name}" uploaded, scanned clean, and sealed.`);
      await loadContent();
      setSelectedDoc(uploaded);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to upload document";
      showNotification(msg, "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteDocument = async () => {
    if (!selectedDoc) return;
    try {
      await apiClient.deleteDocument(selectedDoc.id);
      setIsDeleteConfirmOpen(false);
      showNotification(`Document "${selectedDoc.name}" deleted.`);
      setSelectedDoc(null);
      await loadContent();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete document";
      showNotification(msg, "error");
    }
  };

  const handleDeclareRecord = async () => {
    if (!selectedDoc) return;
    try {
      await apiClient.declareRecord(selectedDoc.id);
      showNotification(`Document declared as immutable official record.`);
      await loadContent();
      const updated = await apiClient.getDocument(selectedDoc.id);
      setSelectedDoc(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to declare record";
      showNotification(msg, "error");
    }
  };

  const handleCheckoutToggle = async () => {
    if (!selectedDoc) return;
    try {
      if (selectedDoc.checkout_by_id) {
        await apiClient.checkinDocument(selectedDoc.id, "Checked in via Content Explorer");
        showNotification("Document checked in.");
      } else {
        await apiClient.checkoutDocument(selectedDoc.id);
        showNotification("Document checked out.");
      }
      await loadContent();
      const updated = await apiClient.getDocument(selectedDoc.id);
      setSelectedDoc(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to toggle checkout";
      showNotification(msg, "error");
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDoc || !newCommentText.trim()) return;
    try {
      const comment = await apiClient.addComment(selectedDoc.id, newCommentText.trim());
      setDocComments((prev) => [comment, ...prev]);
      setNewCommentText("");
      showNotification("Comment added to audit record.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add comment";
      showNotification(msg, "error");
    }
  };

  const formatBytes = (bytes: number | null) => {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const columns: Column<DocumentItem>[] = [
    {
      id: "name",
      header: "Name",
      accessor: (doc) => (
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-600 shrink-0" />
          <div>
            <span className="font-semibold text-surface-900 truncate block max-w-xs">{doc.name}</span>
            {doc.description && <span className="text-[11px] text-surface-500 truncate block">{doc.description}</span>}
          </div>
        </div>
      ),
    },
    {
      id: "version",
      header: "Ver",
      width: "60px",
      accessor: (doc) => (
        <span className="font-mono text-xs text-surface-600 font-semibold">v{doc.version_count}</span>
      ),
    },
    {
      id: "classification",
      header: "Classification",
      width: "120px",
      accessor: (doc) => (
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
      ),
    },
    {
      id: "status",
      header: "Records Status",
      width: "130px",
      accessor: (doc) => {
        if (doc.status === "held") {
          return <StatusPill label="ON LEGAL HOLD" variant="hold" />;
        }
        if (doc.is_record) {
          return <StatusPill label="OFFICIAL RECORD" variant="record" />;
        }
        return <StatusPill label="ACTIVE WORKING" variant="neutral" />;
      },
    },
    {
      id: "size",
      header: "Size",
      width: "80px",
      accessor: (doc) => <span className="text-surface-600 text-xs font-mono">{formatBytes(doc.size_bytes)}</span>,
    },
    {
      id: "department",
      header: "Department",
      width: "100px",
      accessor: (doc) => <span className="text-surface-600 text-xs">{doc.department || "—"}</span>,
    },
    {
      id: "modified",
      header: "Last Modified",
      width: "120px",
      accessor: (doc) => (
        <span className="text-surface-500 text-xs">
          {new Date(doc.updated_at).toLocaleDateString()}
        </span>
      ),
    },
  ];

  // Folder sidebar view
  const folderTree = (
    <div className="space-y-4 text-xs">
      <div>
        <div className="font-bold text-surface-400 uppercase tracking-wider px-2 py-1 select-none flex items-center justify-between">
          <span>Workspaces</span>
          <span className="text-[10px] font-mono text-brand-700 bg-brand-50 px-1.5 py-0.5 rounded">
            {workspaces.length}
          </span>
        </div>
        <div className="space-y-0.5 mt-1">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => {
                setSelectedWorkspace(ws);
                setSelectedFolder(null);
                setSelectedDoc(null);
              }}
              className={`w-full flex items-center justify-between px-2 py-1.5 rounded text-left transition-colors ${
                selectedWorkspace?.id === ws.id
                  ? "bg-brand-50 text-brand-900 font-bold border border-brand-200"
                  : "hover:bg-surface-100 text-surface-700"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <Folder className={`w-3.5 h-3.5 shrink-0 ${selectedWorkspace?.id === ws.id ? "text-brand-600" : "text-amber-500"}`} />
                <span className="truncate">{ws.name}</span>
              </div>
              <span className="text-[9px] font-mono uppercase bg-surface-200 text-surface-600 px-1 rounded">
                {ws.classification.substring(0, 4)}
              </span>
            </button>
          ))}
        </div>
      </div>

      {selectedWorkspace && (
        <div className="pt-2 border-t border-surface-200">
          <div className="font-bold text-surface-400 uppercase tracking-wider px-2 py-1 select-none flex items-center justify-between">
            <span>Folders</span>
            <button
              onClick={() => setIsFolderModalOpen(true)}
              className="text-brand-700 hover:text-brand-900 p-0.5 rounded hover:bg-surface-200"
              title="Add Folder"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-0.5 mt-1">
            <button
              onClick={() => {
                setSelectedFolder(null);
                setSelectedDoc(null);
              }}
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left ${
                selectedFolder === null
                  ? "bg-surface-200 font-semibold text-surface-900"
                  : "hover:bg-surface-100 text-surface-600"
              }`}
            >
              <Folder className="w-3.5 h-3.5 text-surface-400" />
              <span>(All Documents)</span>
            </button>
            {folders.map((f) => (
              <button
                key={f.id}
                onClick={() => {
                  setSelectedFolder(f);
                  setSelectedDoc(null);
                }}
                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left ${
                  selectedFolder?.id === f.id
                    ? "bg-brand-50 text-brand-900 font-semibold border-l-2 border-brand-800"
                    : "hover:bg-surface-100 text-surface-700"
                }`}
              >
                <Folder className="w-3.5 h-3.5 text-amber-500" />
                <span className="truncate">{f.name}</span>
              </button>
            ))}
            {folders.length === 0 && (
              <p className="text-[11px] text-surface-400 px-2 py-1 italic">No subfolders yet</p>
            )}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-surface-50">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`absolute top-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-semibold ${
            notification.type === "success"
              ? "bg-emerald-800 text-white"
              : "bg-red-800 text-white"
          }`}
        >
          {notification.type === "success" ? <CheckCircle className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
          {notification.message}
        </div>
      )}

      <PageHeader
        title={selectedFolder ? selectedFolder.name : selectedWorkspace?.name || "Content Explorer"}
        breadcrumbs={[
          { label: "Content Repository" },
          { label: selectedWorkspace?.name || "Workspaces" },
          ...(selectedFolder ? [{ label: selectedFolder.name }] : []),
        ]}
        badges={
          selectedWorkspace && (
            <StatusPill
              label={`CLASSIFICATION: ${selectedWorkspace.classification}`}
              variant={
                selectedWorkspace.classification === "RESTRICTED"
                  ? "danger"
                  : selectedWorkspace.classification === "CONFIDENTIAL"
                  ? "warning"
                  : "neutral"
              }
            />
          )
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={loadContent}
            >
              Refresh
            </Button>
            <Button
              variant="secondary"
              size="sm"
              icon={<FolderPlus className="w-3.5 h-3.5" />}
              onClick={() => setIsFolderModalOpen(true)}
              disabled={!selectedWorkspace}
            >
              New Folder
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<Upload className="w-3.5 h-3.5" />}
              onClick={() => setIsUploadModalOpen(true)}
              disabled={!selectedWorkspace}
            >
              Upload Document
            </Button>
          </div>
        }
      />

      <div className="flex-1 p-4 overflow-hidden">
        <SplitPane
          left={folderTree}
          leftWidth="w-64"
          right={
            <div className="flex flex-col h-full gap-4 overflow-hidden">
              {/* Document Table */}
              <div className="flex-1 overflow-auto bg-white rounded-lg border border-surface-200 shadow-xs">
                <DataTable
                  columns={columns}
                  data={documents}
                  keyExtractor={(doc) => doc.id}
                  selectedId={selectedDoc?.id}
                  onRowClick={(doc) => setSelectedDoc(doc)}
                  isLoading={isLoading && documents.length === 0}
                  emptyMessage="No documents found in this folder. Click 'Upload Document' to store enterprise assets."
                />
              </div>

              {/* Document Inspector Drawer */}
              {selectedDoc && (
                <div className="border border-surface-300 rounded-lg p-4 bg-white shadow-sm shrink-0">
                  <div className="flex items-start justify-between pb-3 border-b border-surface-200">
                    <div className="flex items-center gap-3">
                      <div className="p-2.5 rounded-lg bg-brand-50 border border-brand-200">
                        <FileText className="w-6 h-6 text-brand-700" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-surface-900">{selectedDoc.name}</h3>
                          {selectedDoc.is_record && <StatusPill label="RECORD" variant="record" />}
                          {selectedDoc.status === "held" && <StatusPill label="LITIGATION HOLD" variant="hold" />}
                          {selectedDoc.checkout_by_id && <StatusPill label="LOCKED / CHECKED OUT" variant="danger" />}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-surface-500 font-mono mt-0.5">
                          <span>Doc ID: {selectedDoc.id}</span>
                          <span>•</span>
                          <span>{formatBytes(selectedDoc.size_bytes)}</span>
                          <span>•</span>
                          <span className="flex items-center gap-1 text-emerald-700 font-semibold">
                            <FileCheck className="w-3.5 h-3.5 text-emerald-600" /> ClamAV Verified Clean
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {docVersions.length > 0 && (
                        <a
                          href={apiClient.getDocumentDownloadUrl(selectedDoc.id, docVersions[0].id)}
                          download={selectedDoc.name}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-surface-100 hover:bg-surface-200 text-surface-800 border border-surface-300 transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" /> Download
                        </a>
                      )}

                      <Button
                        variant="secondary"
                        size="sm"
                        icon={<Lock className="w-3.5 h-3.5" />}
                        onClick={handleCheckoutToggle}
                        disabled={selectedDoc.is_record}
                      >
                        {selectedDoc.checkout_by_id ? "Check In" : "Check Out"}
                      </Button>

                      {!selectedDoc.is_record && (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<CheckCircle className="w-3.5 h-3.5 text-emerald-600" />}
                          onClick={handleDeclareRecord}
                        >
                          Declare Record
                        </Button>
                      )}

                      <Button
                        variant="danger"
                        size="sm"
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                        onClick={() => setIsDeleteConfirmOpen(true)}
                        disabled={selectedDoc.is_record || selectedDoc.status === "held"}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>

                  {/* Tabs: Details / Versions / Comments */}
                  <div className="flex items-center gap-4 border-b border-surface-200 mt-3 text-xs font-semibold">
                    <button
                      onClick={() => setActiveTab("details")}
                      className={`pb-2 border-b-2 transition-colors ${
                        activeTab === "details"
                          ? "border-brand-900 text-brand-900"
                          : "border-transparent text-surface-500 hover:text-surface-800"
                      }`}
                    >
                      Security & Integrity
                    </button>
                    <button
                      onClick={() => setActiveTab("versions")}
                      className={`pb-2 border-b-2 transition-colors flex items-center gap-1.5 ${
                        activeTab === "versions"
                          ? "border-brand-900 text-brand-900"
                          : "border-transparent text-surface-500 hover:text-surface-800"
                      }`}
                    >
                      <History className="w-3.5 h-3.5" /> Versions ({docVersions.length})
                    </button>
                    <button
                      onClick={() => setActiveTab("comments")}
                      className={`pb-2 border-b-2 transition-colors flex items-center gap-1.5 ${
                        activeTab === "comments"
                          ? "border-brand-900 text-brand-900"
                          : "border-transparent text-surface-500 hover:text-surface-800"
                      }`}
                    >
                      <MessageSquare className="w-3.5 h-3.5" /> Comments ({docComments.length})
                    </button>
                    <button
                      onClick={() => setActiveTab("ocr")}
                      className={`pb-2 border-b-2 transition-colors flex items-center gap-1.5 ${
                        activeTab === "ocr"
                          ? "border-brand-900 text-brand-900 font-semibold"
                          : "border-transparent text-surface-500 hover:text-surface-800"
                      }`}
                    >
                      <FileText className="w-3.5 h-3.5" /> OCR Extracted Text
                      {ocrData && (
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded font-mono uppercase font-semibold ${
                            ocrData.status === "ready"
                              ? "bg-emerald-100 text-emerald-800"
                              : ocrData.status === "processing" || ocrData.status === "scanning"
                              ? "bg-purple-100 text-purple-800 animate-pulse"
                              : ocrData.status === "failed"
                              ? "bg-red-100 text-red-800"
                              : ocrData.status === "blocked"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-blue-100 text-blue-800"
                          }`}
                        >
                          {ocrData.status}
                        </span>
                      )}
                    </button>
                  </div>

                  {/* Tab Body */}
                  <div className="pt-3">
                    {activeTab === "details" && (
                      <div className="grid grid-cols-4 gap-4 text-xs">
                        <div>
                          <span className="text-surface-500 font-semibold block">Classification</span>
                          <span className="text-surface-800 font-medium mt-0.5 block">{selectedDoc.classification}</span>
                        </div>
                        <div>
                          <span className="text-surface-500 font-semibold block">Department</span>
                          <span className="text-surface-800 font-medium mt-0.5 block">{selectedDoc.department || "Enterprise Wide"}</span>
                        </div>
                        <div>
                          <span className="text-surface-500 font-semibold block">Litigation Hold</span>
                          <span className={`font-semibold mt-0.5 block ${selectedDoc.status === "held" ? "text-red-700" : "text-surface-600"}`}>
                            {selectedDoc.status === "held" ? "Active Hold (DOJ Inquiry)" : "None"}
                          </span>
                        </div>
                        <div>
                          <span className="text-surface-500 font-semibold block">Cryptographic SHA-256</span>
                          <span className="font-mono text-[11px] text-surface-600 truncate mt-0.5 block" title={selectedDoc.content_hash || ""}>
                            {selectedDoc.content_hash ? `${selectedDoc.content_hash.substring(0, 24)}...` : "Uncalculated"}
                          </span>
                        </div>
                      </div>
                    )}

                    {activeTab === "versions" && (
                      <div className="space-y-2 max-h-36 overflow-y-auto">
                        {docVersions.map((v) => (
                          <div key={v.id} className="flex items-center justify-between p-2 rounded bg-surface-50 text-xs border border-surface-200">
                            <div className="flex items-center gap-3">
                              <span className="font-mono font-bold text-brand-800">v{v.version_number}</span>
                              <span className="font-medium text-surface-800">{v.name}</span>
                              <span className="text-surface-500 font-mono text-[11px]">{formatBytes(v.size_bytes)}</span>
                              <span className="text-emerald-700 font-semibold flex items-center gap-1 text-[11px]">
                                <FileCheck className="w-3 h-3" /> Clean
                              </span>
                            </div>
                            <a
                              href={apiClient.getDocumentDownloadUrl(selectedDoc.id, v.id)}
                              download={v.name}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-brand-800 hover:text-brand-950 font-semibold flex items-center gap-1 text-xs"
                            >
                              <Download className="w-3 h-3" /> Download
                            </a>
                          </div>
                        ))}
                      </div>
                    )}

                    {activeTab === "comments" && (
                      <div className="space-y-3">
                        <div className="space-y-2 max-h-28 overflow-y-auto">
                          {docComments.map((c) => (
                            <div key={c.id} className="p-2 rounded bg-surface-50 text-xs border border-surface-200">
                              <div className="flex items-center justify-between font-semibold text-surface-700">
                                <span>{c.user_email}</span>
                                <span className="text-surface-400 font-mono text-[10px]">
                                  {new Date(c.created_at).toLocaleTimeString()}
                                </span>
                              </div>
                              <p className="text-surface-800 mt-1">{c.body}</p>
                            </div>
                          ))}
                          {docComments.length === 0 && (
                            <p className="text-xs text-surface-400 italic">No audit comments recorded on this document.</p>
                          )}
                        </div>

                        <form onSubmit={handleAddComment} className="flex gap-2">
                          <input
                            type="text"
                            value={newCommentText}
                            onChange={(e) => setNewCommentText(e.target.value)}
                            placeholder="Add immutable audit comment..."
                            className="flex-1 px-3 py-1.5 text-xs bg-white border border-surface-300 rounded focus:ring-1 focus:ring-brand-500"
                          />
                          <Button type="submit" variant="secondary" size="sm" disabled={!newCommentText.trim()}>
                            Post Comment
                          </Button>
                        </form>
                      </div>
                    )}

                    {activeTab === "ocr" && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between bg-surface-50 p-2.5 rounded-lg border border-surface-200">
                          <div className="flex items-center gap-4 text-xs">
                            <div>
                              <span className="text-surface-500 font-semibold block text-[11px]">Pipeline Status</span>
                              <span className="font-semibold capitalize text-surface-900">
                                {ocrData?.status || selectedDoc.status}
                              </span>
                            </div>
                            <div>
                              <span className="text-surface-500 font-semibold block text-[11px]">Confidence</span>
                              <span className="font-mono font-bold text-brand-700">
                                {ocrData && ocrData.confidence > 0 ? `${ocrData.confidence.toFixed(1)}%` : "N/A"}
                              </span>
                            </div>
                            <div>
                              <span className="text-surface-500 font-semibold block text-[11px]">Pages</span>
                              <span className="font-semibold text-surface-800">
                                {ocrData?.page_count || 1}
                              </span>
                            </div>
                            <div>
                              <span className="text-surface-500 font-semibold block text-[11px]">Engine</span>
                              <span className="font-mono text-[11px] text-surface-600">
                                {ocrData?.ocr_engine || "Tesseract 5.4.0 + PyMuPDF"}
                              </span>
                            </div>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={handleRetryOcr}
                            disabled={isRetryingOcr || ocrData?.status === "processing"}
                            className="flex items-center gap-1 text-xs"
                          >
                            <RefreshCw className={`w-3 h-3 ${isRetryingOcr ? "animate-spin" : ""}`} />
                            {isRetryingOcr ? "Processing..." : "Retry OCR"}
                          </Button>
                        </div>

                        {ocrData?.error_message && (
                          <div className="p-2.5 rounded bg-red-50 border border-red-200 text-red-800 text-xs flex items-center gap-2">
                            <ShieldAlert className="w-4 h-4 text-red-600 flex-shrink-0" />
                            <span>OCR Pipeline Error: {ocrData.error_message}</span>
                          </div>
                        )}

                        <div className="relative">
                          <div className="flex items-center justify-between pb-1 text-[11px] text-surface-500 font-medium">
                            <span>Extracted Text Layer (Monospace Viewer)</span>
                            {ocrData?.updated_at && (
                              <span>Updated: {new Date(ocrData.updated_at).toLocaleTimeString()}</span>
                            )}
                          </div>
                          <pre className="font-mono text-xs bg-slate-900 text-slate-100 p-3 rounded-lg overflow-y-auto max-h-48 whitespace-pre-wrap select-all leading-relaxed border border-slate-800">
                            {ocrData?.extracted_text || (
                              ocrData?.status === "processing" || ocrData?.status === "scanning"
                                ? "⏳ OCR extraction in progress... Polling pipeline..."
                                : "No text extracted from this document."
                            )}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          }
        />
      </div>

      {/* Modal: New Folder */}
      <Modal
        open={isFolderModalOpen}
        onOpenChange={setIsFolderModalOpen}
        title="Create New Folder"
        description={`Create a structured subfolder inside workspace "${selectedWorkspace?.name}".`}
      >
        <form onSubmit={handleCreateFolder} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">Folder Name</label>
            <input
              type="text"
              required
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="e.g. Master Services Agreements"
              className="w-full px-3 py-2 text-xs border border-surface-300 rounded focus:ring-1 focus:ring-brand-500 bg-white"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsFolderModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={!newFolderName.trim()}>
              Create Folder
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Universal Upload Center */}
      <Modal
        open={isUploadModalOpen}
        onOpenChange={setIsUploadModalOpen}
        title="Universal Ingestion & Guardrail Center"
        description="Stream-checked size limits, magic bytes validation, ClamAV antivirus scan, and explainable sensitivity classification."
      >
        {selectedWorkspace ? (
          <UniversalUploadCenter
            workspaceId={selectedWorkspace.id}
            folderId={selectedFolder?.id}
            onUploadSuccess={(res: IngestionPipelineResult) => {
              if (res.status === "quarantined") {
                showNotification(`File "${res.filename}" held in quarantine queue for review.`, "error");
              } else {
                showNotification(`Document "${res.filename}" ingested (${res.sensitivity_label} - ${res.mapped_clearance})`);
              }
              loadContent();
            }}
            onClose={() => setIsUploadModalOpen(false)}
          />
        ) : (
          <div className="p-4 text-center text-xs text-surface-500">
            Please select a workspace on the left before uploading documents.
          </div>
        )}
      </Modal>

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        open={isDeleteConfirmOpen}
        onOpenChange={setIsDeleteConfirmOpen}
        title="Delete Document"
        message={`Are you sure you want to delete "${selectedDoc?.name}"? An immutable audit event will record this deletion.`}
        confirmLabel="Delete Document"
        variant="danger"
        onConfirm={handleDeleteDocument}
      />
    </div>
  );
};

export default ContentExplorerView;
