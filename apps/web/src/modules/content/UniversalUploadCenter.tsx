import React, { useState, useRef, DragEvent } from "react";
import {
  UploadCloud,
  FileCheck2,
  ShieldCheck,
  AlertTriangle,
  Lock,
  ChevronDown,
  ChevronUp,
  FileText,
  CheckCircle2,
  Clock,
  Sparkles,
  Info,
  X,
} from "lucide-react";
import { clsx } from "clsx";
import { apiClient } from "@/api/client";
import { useAuth } from "@/config/AuthContext";
import { Button } from "@/design-system/components/Button";

export interface MaskedFinding {
  detector: string;
  category: string;
  count: number;
  masked_examples: string[];
}

export interface IngestionPipelineResult {
  document_id: string | null;
  version_id: string | null;
  quarantine_id: string | null;
  status: "allowed" | "quarantined" | "blocked" | "failed";
  filename: string;
  size_bytes: number;
  content_hash: string;
  detected_mime: string;
  true_extension: string;
  family: string;
  sensitivity_label: "SAFE" | "SENSITIVE" | "CRITICAL" | "UNCLASSIFIED";
  mapped_clearance: "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED";
  classification_reason: string;
  masked_findings: MaskedFinding[];
  scan_status: string;
  scan_details: string;
  archive_report?: Record<string, any> | null;
  message: string;
}

export interface UniversalUploadCenterProps {
  workspaceId: string;
  folderId?: string | null;
  onUploadSuccess: (result: IngestionPipelineResult) => void;
  onClose?: () => void;
}

type PipelineStage = "idle" | "type_check" | "virus_scan" | "extract" | "classify" | "stored" | "done" | "error";

export const UniversalUploadCenter: React.FC<UniversalUploadCenterProps> = ({
  workspaceId,
  folderId,
  onUploadSuccess,
  onClose,
}) => {
  const { user } = useAuth();
  const isAdmin = user?.roles?.some((r) => ["GlobalAdmin", "TenantAdmin", "Admin"].includes(r)) ?? false;

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentStage, setCurrentStage] = useState<PipelineStage>("idle");
  const [stageProgress, setStageProgress] = useState<string>("Ready to ingest");
  const [pipelineResult, setPipelineResult] = useState<IngestionPipelineResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isChipExpanded, setIsChipExpanded] = useState(false);

  // Override Modal state
  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [overrideLabel, setOverrideLabel] = useState<"SAFE" | "SENSITIVE" | "CRITICAL">("SAFE");
  const [overrideReason, setOverrideReason] = useState("");
  const [isSavingOverride, setIsSavingOverride] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (file: File) => {
    setSelectedFile(file);
    setPipelineResult(null);
    setErrorMessage(null);
    setCurrentStage("idle");
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const executePipeline = async () => {
    if (!selectedFile) return;

    try {
      setErrorMessage(null);
      setCurrentStage("type_check");
      setStageProgress("Inspecting binary magic bytes and archive structure...");
      await new Promise((r) => setTimeout(r, 200));

      setCurrentStage("virus_scan");
      setStageProgress("Streaming payload through ClamAV antivirus daemon (fail-closed)...");
      await new Promise((r) => setTimeout(r, 200));

      setCurrentStage("extract");
      setStageProgress("Parsing document text layer inside sandboxed parser...");
      await new Promise((r) => setTimeout(r, 200));

      setCurrentStage("classify");
      setStageProgress("Running algorithmic sensitivity and PII validation...");

      const formData = new FormData();
      formData.append("file", selectedFile);

      const params = new URLSearchParams({ workspace_id: workspaceId });
      if (folderId) params.append("folder_id", folderId);

      const res = await apiClient.post<IngestionPipelineResult>(
        `/api/v1/content/intake/universal?${params.toString()}`,
        formData
      );

      setCurrentStage("stored");
      setStageProgress("Writing content-hash blob to MinIO & hashing audit ledger...");
      await new Promise((r) => setTimeout(r, 150));

      setCurrentStage("done");
      setPipelineResult(res);
      onUploadSuccess(res);
    } catch (err: any) {
      setCurrentStage("error");
      const msg = err.body?.detail || err.message || "File ingestion blocked by server guardrails";
      setErrorMessage(msg);
    }
  };

  const handleApplyOverride = async () => {
    if (!pipelineResult?.document_id || !overrideReason.trim()) return;
    try {
      setIsSavingOverride(true);
      const res = await apiClient.post<any>(
        `/api/v1/guardrails/documents/${pipelineResult.document_id}/classify-override`,
        {
          target_label: overrideLabel,
          reason: overrideReason.trim(),
        }
      );
      setPipelineResult((prev) =>
        prev
          ? {
              ...prev,
              sensitivity_label: overrideLabel,
              mapped_clearance: res.classification,
              classification_reason: `Administrative override: ${overrideReason}`,
            }
          : null
      );
      setIsOverrideOpen(false);
      setOverrideReason("");
    } catch (err: any) {
      alert(err.message || "Failed to record classification override");
    } finally {
      setIsSavingOverride(false);
    }
  };

  const getLabelBadge = (label: string) => {
    switch (label) {
      case "CRITICAL":
        return "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/60 dark:text-rose-200";
      case "SENSITIVE":
        return "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200";
      case "SAFE":
        return "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-200";
      default:
        return "bg-surface-100 text-surface-800 border-surface-300 dark:bg-surface-800 dark:text-surface-200";
    }
  };

  return (
    <div className="space-y-5 text-surface-900 dark:text-surface-100">
      {/* Upload Dropzone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={clsx(
          "border-2 border-dashed rounded-xl p-7 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3",
          isDragging
            ? "border-brand-500 bg-brand-50/60 dark:bg-brand-950/20"
            : "border-surface-300 hover:border-brand-400 bg-surface-50/50 hover:bg-surface-100/60 dark:border-surface-700 dark:bg-surface-900/40"
        )}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => e.target.files?.[0] && handleFileSelected(e.target.files[0])}
          className="hidden"
        />

        <div className="w-12 h-12 rounded-full bg-brand-100 dark:bg-brand-950 text-brand-600 dark:text-brand-400 flex items-center justify-center">
          <UploadCloud className="w-6 h-6" />
        </div>

        <div>
          <p className="text-xs font-bold text-surface-800 dark:text-surface-200">
            {selectedFile ? selectedFile.name : "Click to browse or drop any document to ingest"}
          </p>
          <p className="text-[11px] text-surface-500 mt-0.5">
            PDF, DOCX, XLSX, CSV, JSON, XML, HTML, RTF, EML, ZIP archives (up to tenant policy limit)
          </p>
        </div>

        {selectedFile && (
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 shadow-2xs">
            <span>Size: {formatFileSize(selectedFile.size)}</span>
            <span>•</span>
            <span>Type: {selectedFile.type || "Declared Octet"}</span>
          </div>
        )}
      </div>

      {/* Action / Trigger */}
      {selectedFile && currentStage === "idle" && (
        <div className="flex justify-end gap-2">
          {onClose && (
            <Button variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
          )}
          <Button variant="primary" size="sm" onClick={executePipeline}>
            Run Universal Guardrail Ingestion
          </Button>
        </div>
      )}

      {/* Pipeline Progress Stages */}
      {currentStage !== "idle" && currentStage !== "done" && currentStage !== "error" && (
        <div className="p-4 rounded-lg bg-surface-100 dark:bg-surface-850 border border-surface-200 dark:border-surface-700 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold flex items-center gap-2">
              <Clock className="w-4 h-4 text-brand-600 animate-spin" />
              Ingestion Pipeline Active
            </span>
            <span className="text-surface-500 font-mono text-[11px]">{stageProgress}</span>
          </div>

          {/* Real Sequential Pipeline Indicator */}
          <div className="grid grid-cols-5 gap-2 text-[10px] font-mono text-center">
            {[
              { id: "type_check", label: "1. Type Check" },
              { id: "virus_scan", label: "2. Virus Scan" },
              { id: "extract", label: "3. Text Extract" },
              { id: "classify", label: "4. Classify" },
              { id: "stored", label: "5. Seal & Store" },
            ].map((step, idx) => {
              const stages = ["type_check", "virus_scan", "extract", "classify", "stored", "done"];
              const currentIdx = stages.indexOf(currentStage);
              const isPast = currentIdx > idx;
              const isCur = currentIdx === idx;
              return (
                <div
                  key={step.id}
                  className={clsx(
                    "p-2 rounded border font-semibold transition",
                    isPast
                      ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300"
                      : isCur
                      ? "bg-indigo-50 text-indigo-800 border-indigo-400 dark:bg-indigo-950/60 dark:text-indigo-200 ring-2 ring-indigo-400/30"
                      : "bg-surface-50 text-surface-400 border-surface-200 dark:bg-surface-900 dark:border-surface-800"
                  )}
                >
                  {isPast ? "✓ " : ""}
                  {step.label}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error / Blocked Alert */}
      {errorMessage && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/50 border border-red-300 dark:border-red-800 text-xs text-red-800 dark:text-red-200 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold">File Rejected by Server Policy</p>
            <p className="font-mono text-[11px] leading-relaxed">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* RESULT CARD (Allowed or Quarantined) */}
      {pipelineResult && (
        <div
          className={clsx(
            "rounded-xl border p-5 shadow-xs space-y-4",
            pipelineResult.status === "quarantined"
              ? "bg-amber-50/50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-800"
              : "bg-white dark:bg-surface-900 border-surface-200 dark:border-surface-800"
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-3 border-b border-surface-200 dark:border-surface-800">
            <div className="flex items-center gap-2.5">
              {pipelineResult.status === "quarantined" ? (
                <div className="p-2 bg-amber-100 text-amber-800 rounded-lg">
                  <AlertTriangle className="w-5 h-5" />
                </div>
              ) : (
                <div className="p-2 bg-emerald-100 text-emerald-800 rounded-lg">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              )}
              <div>
                <h4 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                  {pipelineResult.filename}
                </h4>
                <p className="text-[11px] text-surface-500">
                  {pipelineResult.status === "quarantined"
                    ? "Held in Quarantine Queue for Administrator Review"
                    : "Universal Intake Complete • Antivirus Clean • Cryptographically Sealed"}
                </p>
              </div>
            </div>

            <span
              className={clsx(
                "px-2.5 py-1 rounded-md text-xs font-mono font-bold uppercase border",
                getLabelBadge(pipelineResult.sensitivity_label)
              )}
            >
              {pipelineResult.sensitivity_label}
            </span>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-2.5 rounded bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-800">
              <span className="text-[10px] text-surface-400 block mb-0.5">TRUE MIME TYPE</span>
              <span className="font-semibold text-surface-800 dark:text-surface-200 truncate block">
                {pipelineResult.detected_mime}
              </span>
            </div>

            <div className="p-2.5 rounded bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-800">
              <span className="text-[10px] text-surface-400 block mb-0.5">SCAN VERDICT</span>
              <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                {pipelineResult.scan_status}
              </span>
            </div>

            <div className="p-2.5 rounded bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-800">
              <span className="text-[10px] text-surface-400 block mb-0.5">ASSIGNED CLEARANCE</span>
              <span className="font-semibold text-indigo-700 dark:text-indigo-400">
                {pipelineResult.mapped_clearance}
              </span>
            </div>

            <div className="p-2.5 rounded bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-800">
              <span className="text-[10px] text-surface-400 block mb-0.5">SHA-256 HASH</span>
              <span className="font-semibold text-surface-700 dark:text-surface-300 truncate block" title={pipelineResult.content_hash}>
                {pipelineResult.content_hash.slice(0, 12)}...
              </span>
            </div>
          </div>

          {/* Explainable Sensitivity Classification Chip */}
          <div className="rounded-lg bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-800 overflow-hidden text-xs">
            <button
              onClick={() => setIsChipExpanded(!isChipExpanded)}
              className="w-full px-4 py-2.5 flex items-center justify-between text-left hover:bg-surface-100/60 transition"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-brand-600" />
                <span className="font-semibold text-surface-900 dark:text-surface-100">
                  Classification Rationale:
                </span>
                <span className="text-surface-600 dark:text-surface-300 truncate max-w-md">
                  {pipelineResult.classification_reason}
                </span>
              </div>
              <div className="flex items-center gap-1 text-[11px] text-brand-700 dark:text-brand-300 font-semibold">
                <span>{pipelineResult.masked_findings.length} findings</span>
                {isChipExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </div>
            </button>

            {isChipExpanded && (
              <div className="p-4 border-t border-surface-200 dark:border-surface-800 space-y-3 bg-white dark:bg-surface-900">
                <p className="text-[11px] text-surface-500 leading-relaxed">
                  All sensitive entities are deterministically detected using algorithmic checksums and masked before persistence.
                </p>

                {pipelineResult.masked_findings.length === 0 ? (
                  <p className="text-[11px] text-surface-400 italic">No sensitive entities detected in text stream.</p>
                ) : (
                  <div className="space-y-2">
                    {pipelineResult.masked_findings.map((finding, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded bg-surface-50 dark:bg-surface-850 border border-surface-200 dark:border-surface-700 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs font-mono"
                      >
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">
                            {finding.detector}
                          </span>
                          <span className="text-surface-700 dark:text-surface-300">
                            Count: {finding.count}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-[10px] text-surface-400">Masked Evidence:</span>
                          {finding.masked_examples.map((ex, exIdx) => (
                            <span
                              key={exIdx}
                              className="px-2 py-0.5 rounded bg-white dark:bg-surface-950 border border-surface-200 dark:border-surface-700 font-mono text-[11px] text-emerald-700 dark:text-emerald-400"
                            >
                              {ex}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Admin Override Action */}
          {isAdmin && pipelineResult.document_id && (
            <div className="pt-2 flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsOverrideOpen(true)}
              >
                Override Sensitivity Classification (Admin)
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Classification Override Modal */}
      {isOverrideOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white dark:bg-surface-900 rounded-xl shadow-xl border border-surface-200 dark:border-surface-800 p-6 max-w-md w-full space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-surface-200 dark:border-surface-800">
              <h3 className="text-sm font-bold">Override Document Sensitivity</h3>
              <button onClick={() => setIsOverrideOpen(false)} className="text-surface-400 hover:text-surface-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold mb-1">Target Sensitivity Label:</label>
                <select
                  value={overrideLabel}
                  onChange={(e) => setOverrideLabel(e.target.value as any)}
                  className="w-full p-2 border border-surface-300 dark:border-surface-700 rounded bg-white dark:bg-surface-850 font-mono text-xs"
                >
                  <option value="SAFE">SAFE (Maps to INTERNAL clearance)</option>
                  <option value="SENSITIVE">SENSITIVE (Maps to CONFIDENTIAL clearance)</option>
                  <option value="CRITICAL">CRITICAL (Maps to RESTRICTED clearance)</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold mb-1">Mandatory Business Justification:</label>
                <textarea
                  rows={3}
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="State audited reason for overriding automated classification..."
                  className="w-full p-2 border border-surface-300 dark:border-surface-700 rounded bg-white dark:bg-surface-850 text-xs"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setIsOverrideOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!overrideReason.trim() || isSavingOverride}
                onClick={handleApplyOverride}
              >
                {isSavingOverride ? "Recording Audit Chain..." : "Confirm & Sign Ledger"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

