import React, { useState, useEffect } from "react";
import {
  Cpu,
  RefreshCw,
  Sparkles,
  FileText,
  Layers,
  BookOpen,
  Type,
  Sun,
  Eye,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Sliders,
  Zap,
} from "lucide-react";
import { clsx } from "clsx";
import { apiClient } from "@/api/client";
import { useAuth } from "@/config/AuthContext";

interface BenchmarkStats {
  cer?: number | null;
  wer?: number | null;
  field_f1?: number | null;
  gstin_accuracy?: number | null;
  pages_per_sec?: number | null;
  run_date?: string | null;
}

interface OcrEngineCardData {
  id: string;
  name: string;
  icon: string;
  license: string;
  model_revision: string;
  capabilities: string[];
  description: string;
  is_installed: boolean;
  version: string | null;
  status: string;
  is_enabled: boolean;
  priority: number;
  digital_weight: number;
  scanned_weight: number;
  custom_settings: Record<string, any>;
  benchmark: BenchmarkStats | null;
}

interface RoutingPolicy {
  version: number;
  default_engine: string;
  fallback_engine: string;
  rules: Array<{ condition: string; engine: string; description?: string }>;
  created_at: string;
}

export const OcrEnginesControlCenterView: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.roles?.some((r) =>
    ["GlobalAdmin", "TenantAdmin", "Admin"].includes(r)
  ) ?? true;

  const [engines, setEngines] = useState<OcrEngineCardData[]>([]);
  const [policy, setPolicy] = useState<RoutingPolicy | null>(null);
  const [policyHistory, setPolicyHistory] = useState<any[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Test Modal State
  const [testingEngine, setTestingEngine] = useState<OcrEngineCardData | null>(null);
  const [testSampleId, setTestSampleId] = useState("clean_invoice");
  const [testFile, setTestFile] = useState<File | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<any | null>(null);

  // Policy Sandbox State
  const [simPdf, setSimPdf] = useState(true);
  const [simTextLayer, setSimTextLayer] = useState(true);
  const [simLang, setSimLang] = useState("eng");
  const [simScanned, setSimScanned] = useState(false);
  const [simResult, setSimResult] = useState<any | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  // Benchmark Run State
  const [benchmarkingEngineId, setBenchmarkingEngineId] = useState<string | null>(null);

  const fetchEngines = async () => {
    try {
      setIsRefreshing(true);
      const res = await apiClient.get<any>("/api/v1/idp/engines/status");
      if (res && res.engines) {
        setEngines(res.engines);
      }
      const polRes = await apiClient.get<any>("/api/v1/idp/engines/routing-policy");
      if (polRes) {
        setPolicy(polRes.active_policy);
        setPolicyHistory(polRes.history || []);
      }
      setErrorMessage(null);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load OCR engine configurations");
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchEngines();
  }, []);

  const handleToggle = async (engineId: string, currentEnabled: boolean) => {
    if (!isAdmin) return;
    try {
      const nextState = !currentEnabled;
      setEngines((prev) =>
        prev.map((e) => (e.id === engineId ? { ...e, is_enabled: nextState } : e))
      );
      await apiClient.post(`/api/v1/idp/engines/${engineId}/toggle`, {
        is_enabled: nextState,
      });
      setSuccessMessage(`Engine ${engineId} is now ${nextState ? "enabled" : "disabled"}`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to toggle engine");
      fetchEngines();
    }
  };

  const handleWeightChange = async (
    engineId: string,
    field: "digital_weight" | "scanned_weight" | "priority",
    value: number
  ) => {
    if (!isAdmin) return;
    setEngines((prev) =>
      prev.map((e) => (e.id === engineId ? { ...e, [field]: value } : e))
    );
    const target = engines.find((e) => e.id === engineId);
    if (!target) return;

    try {
      await apiClient.post(`/api/v1/idp/engines/${engineId}/config`, {
        priority: field === "priority" ? value : target.priority,
        digital_weight: field === "digital_weight" ? value : target.digital_weight,
        scanned_weight: field === "scanned_weight" ? value : target.scanned_weight,
        custom_settings: target.custom_settings,
      });
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to update engine parameters");
    }
  };

  const handleRunBenchmark = async (engineId: string) => {
    if (!isAdmin) return;
    setBenchmarkingEngineId(engineId);
    try {
      const res = await apiClient.post<any>(`/api/v1/idp/engines/${engineId}/benchmark`);
      setSuccessMessage(`Benchmark complete for ${engineId}! CER: ${res.cer}%, WER: ${res.wer}%`);
      setTimeout(() => setSuccessMessage(null), 4000);
      fetchEngines();
    } catch (err: any) {
      setErrorMessage(err.message || `Benchmark failed for ${engineId}`);
    } finally {
      setBenchmarkingEngineId(null);
    }
  };

  const handleRunTest = async () => {
    if (!testingEngine) return;
    setIsTesting(true);
    setTestResult(null);
    try {
      let res;
      if (testFile) {
        const formData = new FormData();
        formData.append("file", testFile);
        res = await apiClient.post<any>(`/api/v1/idp/engines/${testingEngine.id}/test`, formData);
      } else {
        res = await apiClient.post<any>(
          `/api/v1/idp/engines/${testingEngine.id}/test?sample_id=${testSampleId}`
        );
      }
      setTestResult(res);
    } catch (err: any) {
      setErrorMessage(err.message || "Engine test execution failed");
    } finally {
      setIsTesting(false);
    }
  };

  const handleSimulatePolicy = async () => {
    setIsSimulating(true);
    try {
      const res = await apiClient.post<any>("/api/v1/idp/engines/routing-policy/test", {
        is_pdf: simPdf,
        has_text_layer: simTextLayer,
        language: simLang,
        is_scanned: simScanned,
      });
      setSimResult(res);
    } catch (err: any) {
      setErrorMessage(err.message || "Policy simulation failed");
    } finally {
      setIsSimulating(false);
    }
  };

  const handleRollbackPolicy = async () => {
    if (!isAdmin) return;
    try {
      await apiClient.post("/api/v1/idp/engines/routing-policy/rollback", {});
      setSuccessMessage("Successfully rolled back to previous OCR routing policy!");
      setTimeout(() => setSuccessMessage(null), 3000);
      fetchEngines();
    } catch (err: any) {
      setErrorMessage(err.message || "Rollback failed");
    }
  };

  const renderIcon = (name: string) => {
    switch (name) {
      case "FileText":
        return <FileText className="w-5 h-5 text-sky-500" />;
      case "Sparkles":
        return <Sparkles className="w-5 h-5 text-purple-500" />;
      case "Layers":
        return <Layers className="w-5 h-5 text-indigo-500" />;
      case "BookOpen":
        return <BookOpen className="w-5 h-5 text-amber-500" />;
      case "Type":
        return <Type className="w-5 h-5 text-emerald-500" />;
      case "Sun":
        return <Sun className="w-5 h-5 text-orange-500" />;
      case "Eye":
        return <Eye className="w-5 h-5 text-teal-500" />;
      case "Cpu":
      default:
        return <Cpu className="w-5 h-5 text-brand-500" />;
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-surface-50 dark:bg-surface-950">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-surface-200 dark:border-surface-800">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-50 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-800 rounded-lg text-brand-600">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
                OCR Engines Control Center
              </h1>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Multi-Tenant Dynamic Engine Orchestration, Real Accuracy Benchmarks & Automated Failover Policies
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchEngines}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-surface-700 dark:text-surface-300 bg-white dark:bg-surface-900 border border-surface-300 dark:border-surface-700 rounded-md hover:bg-surface-50 shadow-sm transition"
          >
            <RefreshCw className={clsx("w-3.5 h-3.5", isRefreshing && "animate-spin")} />
            Refresh Engines Status
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMessage && (
        <div className="p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="font-bold ml-2">✕</button>
        </div>
      )}
      {successMessage && (
        <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900 rounded-lg text-xs text-emerald-700 dark:text-emerald-300 flex items-center justify-between">
          <span>{successMessage}</span>
          <button onClick={() => setSuccessMessage(null)} className="font-bold ml-2">✕</button>
        </div>
      )}

      {/* Status Bar Pills */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-lg shadow-sm">
          <span className="text-[11px] text-surface-500 uppercase font-semibold">Total Engine Adapters</span>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{engines.length || 8}</p>
        </div>
        <div className="p-3 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-lg shadow-sm">
          <span className="text-[11px] text-surface-500 uppercase font-semibold">Operational & Installed</span>
          <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
            {engines.filter((e) => e.is_installed).length} / {engines.length || 8}
          </p>
        </div>
        <div className="p-3 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-lg shadow-sm">
          <span className="text-[11px] text-surface-500 uppercase font-semibold">Active In Router</span>
          <p className="text-lg font-bold text-brand-600 dark:text-brand-400">
            {engines.filter((e) => e.is_enabled).length} Enabled
          </p>
        </div>
        <div className="p-3 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-lg shadow-sm">
          <span className="text-[11px] text-surface-500 uppercase font-semibold">Active Policy Version</span>
          <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
            v{policy?.version || 1} ({policy?.default_engine || "tesseract"})
          </p>
        </div>
      </div>

      {/* Engine Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        {engines.map((eng) => {
          const isBenchmarking = benchmarkingEngineId === eng.id;
          return (
            <div
              key={eng.id}
              className={clsx(
                "flex flex-col justify-between bg-white dark:bg-surface-900 border rounded-xl p-4 shadow-sm transition hover:shadow-md",
                eng.is_enabled
                  ? "border-surface-200 dark:border-surface-700"
                  : "border-surface-200/60 dark:border-surface-800/60 opacity-80"
              )}
            >
              <div>
                {/* Header */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-surface-100 dark:bg-surface-800 rounded-lg">
                      {renderIcon(eng.icon)}
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 leading-tight">
                        {eng.name}
                      </h3>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[10px] text-surface-500 font-mono">
                          Pri: #{eng.priority}
                        </span>
                        <span className="text-surface-300 dark:text-surface-700">•</span>
                        <span className="text-[10px] text-surface-500 uppercase font-medium">
                          {eng.license}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Toggle Switch */}
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={eng.is_enabled}
                      disabled={!isAdmin || !eng.is_installed}
                      onChange={() => handleToggle(eng.id, eng.is_enabled)}
                      className="sr-only peer"
                    />
                    <div className="w-8 h-4 bg-surface-200 peer-focus:outline-none rounded-full peer dark:bg-surface-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-surface-600 peer-checked:bg-brand-600"></div>
                  </label>
                </div>

                {/* Status Pill */}
                <div className="mb-3">
                  <span
                    className={clsx(
                      "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium",
                      eng.is_installed
                        ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                        : "bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400 border border-surface-200 dark:border-surface-700"
                    )}
                  >
                    {eng.is_installed ? (
                      <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                    ) : (
                      <AlertTriangle className="w-3 h-3 text-surface-400" />
                    )}
                    {eng.status}
                  </span>
                </div>

                {/* Description */}
                <p className="text-xs text-surface-600 dark:text-surface-400 mb-3 line-clamp-2">
                  {eng.description}
                </p>

                {/* Capability Badges */}
                <div className="flex flex-wrap gap-1 mb-4">
                  {eng.capabilities.map((cap, i) => (
                    <span
                      key={i}
                      className="px-1.5 py-0.5 text-[10px] bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-300 rounded border border-surface-200 dark:border-surface-700"
                    >
                      {cap}
                    </span>
                  ))}
                </div>

                {/* Weights Sliders */}
                <div className="space-y-2 p-2.5 bg-surface-50 dark:bg-surface-800/40 rounded-lg border border-surface-100 dark:border-surface-800 mb-4">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-surface-500 font-medium">Digital PDF Wt:</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={eng.digital_weight}
                      disabled={!isAdmin}
                      onChange={(e) =>
                        handleWeightChange(eng.id, "digital_weight", parseFloat(e.target.value))
                      }
                      className="w-20 h-1.5 accent-brand-600 cursor-pointer"
                    />
                    <span className="font-mono text-surface-700 dark:text-surface-300 w-8 text-right">
                      {eng.digital_weight.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-surface-500 font-medium">Scanned Wt:</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={eng.scanned_weight}
                      disabled={!isAdmin}
                      onChange={(e) =>
                        handleWeightChange(eng.id, "scanned_weight", parseFloat(e.target.value))
                      }
                      className="w-20 h-1.5 accent-purple-600 cursor-pointer"
                    />
                    <span className="font-mono text-surface-700 dark:text-surface-300 w-8 text-right">
                      {eng.scanned_weight.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Real Measured Accuracy Block */}
                <div className="p-2.5 bg-surface-50 dark:bg-surface-800/40 rounded-lg border border-surface-100 dark:border-surface-800 mb-4">
                  <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-surface-200/50 dark:border-surface-700/50">
                    <span className="text-[10px] font-bold text-surface-400 uppercase tracking-wider">
                      Measured Accuracy & Speed
                    </span>
                    <span className="text-[9px] text-surface-400 font-mono">
                      {eng.benchmark?.run_date ? eng.benchmark.run_date.split("T")[0] : "Held-Out Set"}
                    </span>
                  </div>

                  {eng.benchmark ? (
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <span className="text-surface-500 block text-[10px]">Overall CER</span>
                        <span className="font-mono font-semibold text-brand-600 dark:text-brand-400">
                          {eng.benchmark.cer !== null ? `${eng.benchmark.cer}%` : "—"}
                        </span>
                      </div>
                      <div>
                        <span className="text-surface-500 block text-[10px]">Field F1</span>
                        <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                          {eng.benchmark.field_f1 !== null ? `${eng.benchmark.field_f1}%` : "—"}
                        </span>
                      </div>
                      <div>
                        <span className="text-surface-500 block text-[10px]">GSTIN Accuracy</span>
                        <span className="font-mono font-semibold text-purple-600 dark:text-purple-400">
                          {eng.benchmark.gstin_accuracy !== null ? `${eng.benchmark.gstin_accuracy}%` : "—"}
                        </span>
                      </div>
                      <div>
                        <span className="text-surface-500 block text-[10px]">Throughput</span>
                        <span className="font-mono font-semibold text-surface-800 dark:text-surface-200">
                          {eng.benchmark.pages_per_sec !== null ? `${eng.benchmark.pages_per_sec} p/s` : "—"}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-2 text-surface-400 text-xs italic">
                      Not benchmarked yet
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-2 border-t border-surface-100 dark:border-surface-800">
                <button
                  onClick={() => {
                    setTestingEngine(eng);
                    setTestResult(null);
                  }}
                  className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-surface-700 dark:text-surface-300 bg-white dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-md hover:bg-surface-50 dark:hover:bg-surface-700 transition"
                >
                  <Play className="w-3 h-3 text-brand-500" />
                  Test
                </button>
                <button
                  onClick={() => handleRunBenchmark(eng.id)}
                  disabled={!isAdmin || !eng.is_installed || isBenchmarking}
                  className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-brand-700 dark:text-brand-300 bg-brand-50 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-800 rounded-md hover:bg-brand-100 dark:hover:bg-brand-900/40 transition disabled:opacity-50"
                >
                  <RefreshCw className={clsx("w-3 h-3", isBenchmarking && "animate-spin")} />
                  {isBenchmarking ? "Running..." : "Benchmark"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Global Routing Policy Editor & Simulator */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-4">
        {/* Policy Editor */}
        <div className="lg:col-span-2 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-surface-200 dark:border-surface-800 mb-4">
            <div className="flex items-center gap-2">
              <Sliders className="w-5 h-5 text-purple-600" />
              <div>
                <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                  Adaptive OCR Routing Policy (v{policy?.version || 1})
                </h2>
                <p className="text-xs text-surface-500">
                  Dynamic condition matching with instant fallback cascade
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleRollbackPolicy}
                disabled={!isAdmin || policyHistory.length <= 1}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-surface-600 dark:text-surface-300 bg-surface-100 dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-md hover:bg-surface-200 disabled:opacity-40 transition"
              >
                <RotateCcw className="w-3 h-3" />
                Rollback Policy
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
                  Default Primary Engine
                </label>
                <select
                  value={policy?.default_engine || "tesseract"}
                  disabled={!isAdmin}
                  className="w-full text-xs bg-surface-50 dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-md p-2"
                >
                  <option value="tesseract">Tesseract (Production Workhorse)</option>
                  <option value="indra">Indra OCR (Transformer)</option>
                  <option value="pymupdf">PyMuPDF (Text Layer)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
                  Failover Fallback Engine
                </label>
                <select
                  value={policy?.fallback_engine || "tesseract"}
                  disabled={!isAdmin}
                  className="w-full text-xs bg-surface-50 dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-md p-2"
                >
                  <option value="tesseract">Tesseract (Safe Fallback)</option>
                  <option value="indra">Indra OCR</option>
                  <option value="pymupdf">PyMuPDF</option>
                </select>
              </div>
            </div>

            {/* Rules Table */}
            <div>
              <span className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-2">
                Active Routing Rules
              </span>
              <div className="border border-surface-200 dark:border-surface-800 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface-50 dark:bg-surface-800/60 text-surface-500 border-b border-surface-200 dark:border-surface-800">
                    <tr>
                      <th className="py-2 px-3">Condition</th>
                      <th className="py-2 px-3">Description</th>
                      <th className="py-2 px-3">Target Engine</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
                    {policy?.rules?.map((r, i) => (
                      <tr key={i} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30">
                        <td className="py-2 px-3 font-mono text-[11px] text-brand-600 dark:text-brand-400">
                          {r.condition}
                        </td>
                        <td className="py-2 px-3 text-surface-600 dark:text-surface-400">
                          {r.description || "Automatic condition match"}
                        </td>
                        <td className="py-2 px-3">
                          <span className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 font-mono text-[11px]">
                            {r.engine}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* Policy Sandbox Simulator */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center gap-2 pb-3 border-b border-surface-200 dark:border-surface-800 mb-4">
            <Zap className="w-5 h-5 text-amber-500" />
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                Routing Policy Sandbox
              </h2>
              <p className="text-xs text-surface-500">Simulate routing decisions live</p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-surface-600 dark:text-surface-400">Is PDF File?</span>
              <input
                type="checkbox"
                checked={simPdf}
                onChange={(e) => setSimPdf(e.target.checked)}
                className="accent-brand-600"
              />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-surface-600 dark:text-surface-400">Has Vector Text Layer?</span>
              <input
                type="checkbox"
                checked={simTextLayer}
                onChange={(e) => setSimTextLayer(e.target.checked)}
                className="accent-brand-600"
              />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-surface-600 dark:text-surface-400">Is Scanned / Image?</span>
              <input
                type="checkbox"
                checked={simScanned}
                onChange={(e) => setSimScanned(e.target.checked)}
                className="accent-brand-600"
              />
            </div>
            <div>
              <label className="block text-xs text-surface-600 dark:text-surface-400 mb-1">
                Detected Script / Language
              </label>
              <select
                value={simLang}
                onChange={(e) => setSimLang(e.target.value)}
                className="w-full text-xs bg-surface-50 dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-md p-1.5"
              >
                <option value="eng">English (Latin)</option>
                <option value="hin">Hindi / Indic (Devanagari)</option>
                <option value="fra">French / European</option>
              </select>
            </div>

            <button
              onClick={handleSimulatePolicy}
              disabled={isSimulating}
              className="w-full py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-md text-xs font-semibold shadow-sm transition mt-2"
            >
              {isSimulating ? "Evaluating Rules..." : "Test Policy Routing"}
            </button>

            {simResult && (
              <div className="p-3 bg-purple-50 dark:bg-purple-950/40 border border-purple-200 dark:border-purple-800 rounded-lg text-xs space-y-1.5 mt-3">
                <div className="flex items-center justify-between">
                  <span className="text-surface-500">Selected Engine:</span>
                  <span className="font-bold text-purple-700 dark:text-purple-300 uppercase">
                    {simResult.selected_engine}
                  </span>
                </div>
                <div className="text-[11px] text-surface-600 dark:text-surface-400">
                  <span className="font-medium">Reason: </span>
                  {simResult.decision_reason}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Test Modal */}
      {testingEngine && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-800">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-brand-500" />
                <h3 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                  Test OCR Engine: {testingEngine.name}
                </h3>
              </div>
              <button
                onClick={() => setTestingEngine(null)}
                className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-200"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-4 overflow-y-auto flex-1 text-xs">
              <div>
                <label className="block font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Select Bundled Sample Document
                </label>
                <select
                  value={testSampleId}
                  onChange={(e) => {
                    setTestSampleId(e.target.value);
                    setTestFile(null);
                  }}
                  className="w-full bg-surface-50 dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-md p-2"
                >
                  <option value="clean_invoice">Clean Enterprise Invoice (300 DPI)</option>
                  <option value="degraded_invoice">Degraded Invoice (Skew + Blur + Contrast)</option>
                  <option value="receipt">Thermal Retail Receipt</option>
                  <option value="contract">Legal Agreement / Contract</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-surface-700 dark:text-surface-300 mb-1">
                  Or Upload Custom Document / PDF
                </label>
                <input
                  type="file"
                  onChange={(e) => setTestFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-surface-500 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-surface-100 file:text-surface-700 hover:file:bg-surface-200"
                />
              </div>

              <button
                onClick={handleRunTest}
                disabled={isTesting}
                className="w-full py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-md font-semibold transition"
              >
                {isTesting ? "Executing Engine..." : "Run Test OCR"}
              </button>

              {testResult && (
                <div className="space-y-3 pt-3 border-t border-surface-200 dark:border-surface-800">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-2 bg-surface-50 dark:bg-surface-800 rounded">
                      <span className="text-[10px] text-surface-500 block">Latency</span>
                      <span className="font-mono font-bold text-surface-900 dark:text-surface-100">
                        {testResult.execution_time_ms} ms
                      </span>
                    </div>
                    <div className="p-2 bg-surface-50 dark:bg-surface-800 rounded">
                      <span className="text-[10px] text-surface-500 block">Confidence</span>
                      <span className="font-mono font-bold text-emerald-600">
                        {testResult.mean_confidence}%
                      </span>
                    </div>
                    <div className="p-2 bg-surface-50 dark:bg-surface-800 rounded">
                      <span className="text-[10px] text-surface-500 block">Words Found</span>
                      <span className="font-mono font-bold text-purple-600">
                        {testResult.total_words}
                      </span>
                    </div>
                  </div>

                  <div>
                    <span className="block font-medium text-surface-700 dark:text-surface-300 mb-1">
                      Raw Extracted Text (Preview)
                    </span>
                    <pre className="p-3 bg-surface-100 dark:bg-surface-950 rounded border border-surface-200 dark:border-surface-800 font-mono text-[11px] max-h-48 overflow-y-auto whitespace-pre-wrap">
                      {testResult.full_text || "(No text detected)"}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
