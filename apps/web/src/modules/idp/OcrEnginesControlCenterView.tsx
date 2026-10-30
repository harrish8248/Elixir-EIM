import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Cpu,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Save,
  Battery,
  Sliders,
  ShieldCheck,
  Activity,
  Gauge,
  Check,
} from "lucide-react";
import { clsx } from "clsx";
import { apiClient } from "@/api/client";
import { useAuth } from "@/config/AuthContext";

interface BenchmarkStats {
  cer: number | null;
  wer: number | null;
  field_f1: number | null;
  gstin_accuracy: number | null;
  pages_per_sec: number | null;
  run_date: string | null;
}

interface EngineResourceProfileData {
  engine_id: string;
  device_support: string;
  min_ram_mb: number;
  typical_ram_mb: number;
  min_vram_mb: number;
  disk_size_mb: number;
  model_load_time_sec?: number;
  default_threads?: number;
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
  resource_profile?: EngineResourceProfileData | null;
}

interface RoutingPolicy {
  version: number;
  default_engine: string;
  fallback_engine: string;
  rules: Array<{ condition: string; engine: string; description?: string }>;
  created_at: string;
}

const DEFAULT_YAML_POLICY = `# Elixir EIM Adaptive Routing Policy v7
defaults:
  confidence_threshold: 0.85   # Threshold below which critic initiates failover
  field_threshold: 0.80        # Any key field below this -> human validation
  max_engine_attempts: 3
rules:
  - when: file.type in [xlsx, xls, csv]         use: pymupdf      # Structured table stream
  - when: pdf.text_coverage >= 0.85             use: pymupdf      # Born-digital PDF vector layer
  - when: language in [hi, dev, bn, indic]      use: indra        # Indic & Devanagari clean print
  - when: complexity_score <= 40                use: tesseract    # OpenCV deskew + CLAHE filter
  - when: complexity_score <= 75                use: paddleocr    # Deep learning multilingual
  - when: complexity_score > 75                 use: ollama       # Local multimodal vision LLM
  - when: handwriting or novel_layout           use: ollama       # Zero-shot visual reasoning
fallback_order: [pymupdf, indra, tesseract, paddleocr, human_review]
pins:
  - sender: "*@ups.com"                         engine: pymupdf   # Logistics born-digital bills
  - sender: "*@fedex.com"                       engine: pymupdf
guardrails:
  max_cost_per_page: 0.00                       # 100% self-hosted on-prem execution
  throttle_on_battery: true                     # Throttles neural passes when on laptop battery`;

const ROUTER_PRESETS: Record<string, { label: string; json: string }> = {
  po_skewed: {
    label: "Phone photo of customer PO (Skewed, 150 DPI, Shadowed)",
    json: JSON.stringify(
      {
        photo: true,
        dpi: 150,
        skewDeg: 4,
        pages: 1,
        language: "en",
        sender: "procurement@supplier.example",
      },
      null,
      2
    ),
  },
  digital_pdf: {
    label: "Born-digital ERP Invoice (Vector Text Layer Present)",
    json: JSON.stringify(
      {
        file_type: "pdf",
        has_text_layer: true,
        pdf_text_coverage: 0.96,
        language: "en",
        sender: "billing@acrocorp.com",
      },
      null,
      2
    ),
  },
  indic_devanagari: {
    label: "Indic / Devanagari Hindi Tax Invoice (Clean Print)",
    json: JSON.stringify(
      {
        language: "hin",
        script: "Devanagari",
        has_text_layer: false,
        dpi: 300,
        pages: 1,
        sender: "vendor.delhi@gov.in",
      },
      null,
      2
    ),
  },
  table_heavy: {
    label: "Multi-page Scanned PO with Dense 40-Row Table (300 DPI)",
    json: JSON.stringify(
      {
        file_type: "pdf",
        pages: 4,
        complexity_score: 65,
        table_heavy: true,
        dpi: 300,
        sender: "hardware.supplies@mfg.com",
      },
      null,
      2
    ),
  },
  complex_contract: {
    label: "Complex Contract with Handwriting & Stamped Seals (Needs LLM)",
    json: JSON.stringify(
      {
        complexity_score: 85,
        handwriting: true,
        must_use_llm: true,
        pages: 2,
        sender: "legal.counsel@enterprise.org",
      },
      null,
      2
    ),
  },
};

// Engine metadata with hardware performance mappings
const ENGINE_METRICS: Record<
  string,
  {
    arch: string;
    deviceType: string;
    deviceBadgeColor: string;
    ramFootprint: string;
    speedEstimate: string;
    f1Score: string;
    bestFor: string;
  }
> = {
  pymupdf: {
    arch: "Vector PDF Parser",
    deviceType: "CPU Only",
    deviceBadgeColor: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300",
    ramFootprint: "~200 MB",
    speedEstimate: "0.08 s",
    f1Score: "99.8%",
    bestFor: "Born-digital PDFs, invoices from ERP, native text streams",
  },
  tesseract: {
    arch: "LSTM Neural + OpenCV",
    deviceType: "CPU (Multi-Threaded)",
    deviceBadgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300",
    ramFootprint: "~350 MB",
    speedEstimate: "1.20 s",
    f1Score: "94.2%",
    bestFor: "Scanned documents, phone photos with deskew/CLAHE, Latin & Indic",
  },
  indra: {
    arch: "ONNX Transformer",
    deviceType: "CPU ONNX Runtime",
    deviceBadgeColor: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/60 dark:text-purple-300",
    ramFootprint: "~600 MB",
    speedEstimate: "0.65 s",
    f1Score: "97.4%",
    bestFor: "Indic scripts, Devanagari, Bengali, Tamil, Cyrillic, Greek",
  },
  paddleocr: {
    arch: "DBNet + SVTR",
    deviceType: "CPU / GPU",
    deviceBadgeColor: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300",
    ramFootprint: "~1,500 MB",
    speedEstimate: "2.40 s",
    f1Score: "95.8%",
    bestFor: "Multilingual text lines, arbitrary angles, Asian scripts",
  },
  doctr: {
    arch: "DBNet + CRNN",
    deviceType: "CPU / GPU",
    deviceBadgeColor: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300",
    ramFootprint: "~2,000 MB",
    speedEstimate: "2.90 s",
    f1Score: "95.1%",
    bestFor: "Document layout detection and end-to-end reading order",
  },
  easyocr: {
    arch: "CRAFT + ResNet",
    deviceType: "PyTorch CPU",
    deviceBadgeColor: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/60 dark:text-sky-300",
    ramFootprint: "~1,200 MB",
    speedEstimate: "1.85 s",
    f1Score: "92.0%",
    bestFor: "Natural scene text, cropped bounding boxes, receipts",
  },
  surya: {
    arch: "Vision Transformer",
    deviceType: "GPU / High-RAM CPU",
    deviceBadgeColor: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300",
    ramFootprint: "~2,500 MB",
    speedEstimate: "3.20 s",
    f1Score: "96.5%",
    bestFor: "Complex multi-column layouts, reading order estimation",
  },
  ollama: {
    arch: "Local Multimodal LLM",
    deviceType: "Ollama Daemon",
    deviceBadgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300",
    ramFootprint: "~4,000 MB",
    speedEstimate: "4.50 s",
    f1Score: "98.2%",
    bestFor: "Handwritten invoices, unstructured tables, zero-shot visual QA",
  },
};

export const OcrEnginesControlCenterView: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.roles?.some((r) =>
    ["GlobalAdmin", "TenantAdmin", "Admin"].includes(r)
  ) ?? true;

  const [engines, setEngines] = useState<OcrEngineCardData[]>([]);
  const [hardware, setHardware] = useState<any | null>(null);
  const [policy, setPolicy] = useState<RoutingPolicy | null>(null);
  const [policyHistory, setPolicyHistory] = useState<any[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Power Mode Selection: "AUTO" | "ECO" | "PERFORMANCE"
  const [powerMode, setPowerMode] = useState<"AUTO" | "ECO" | "PERFORMANCE">("AUTO");

  // Policy View Mode: "visual" | "yaml"
  const [policyTab, setPolicyTab] = useState<"visual" | "yaml">("visual");

  // Routing Policy YAML editor state
  const [yamlPolicy, setYamlPolicy] = useState<string>(DEFAULT_YAML_POLICY);
  const [isSavingPolicy, setIsSavingPolicy] = useState(false);

  // Simulator state
  const [selectedPresetKey, setSelectedPresetKey] = useState<string>("po_skewed");
  const [profileJsonText, setProfileJsonText] = useState<string>(ROUTER_PRESETS.po_skewed.json);
  const [isAskingRouter, setIsAskingRouter] = useState(false);
  const [routerDecision, setRouterDecision] = useState<any | null>(null);

  // Test Modal State
  const [testingEngine, setTestingEngine] = useState<OcrEngineCardData | null>(null);
  const [testSampleId, setTestSampleId] = useState("clean_invoice");
  const [testFile, setTestFile] = useState<File | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [benchmarkingEngineId, setBenchmarkingEngineId] = useState<string | null>(null);

  const fetchEngines = async () => {
    try {
      setIsRefreshing(true);
      const res = await apiClient.get<any>("/api/v1/idp/engines/status");
      if (res && res.engines) {
        setEngines(res.engines);
      }
      if (res && res.hardware) {
        setHardware(res.hardware);
      }
      // Also fetch hardware directly if not bundled
      const hwRes = await apiClient.get<any>("/api/v1/idp/hardware").catch(() => null);
      if (hwRes) {
        setHardware(hwRes);
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
    const targetEng = engines.find((e) => e.id === engineId);
    const nextState = !currentEnabled;
    try {
      setEngines((prev) =>
        prev.map((e) => (e.id === engineId ? { ...e, is_enabled: nextState } : e))
      );
      await apiClient.post(`/api/v1/idp/engines/${engineId}/toggle`, {
        is_enabled: nextState,
      });
      if (nextState && targetEng && !targetEng.is_installed) {
        setSuccessMessage(
          `${targetEng.name} enabled in routing policy. (Package is standing by for download; will auto-fallback until dependencies are present).`
        );
      } else {
        setSuccessMessage(`Engine ${targetEng?.name || engineId} is now ${nextState ? "activated" : "deactivated"}`);
      }
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to toggle engine");
      fetchEngines();
    }
  };

  const handleRunBenchmark = async (engineId: string) => {
    if (!isAdmin) return;
    const targetEng = engines.find((e) => e.id === engineId);
    if (targetEng && !targetEng.is_installed) {
      setErrorMessage(`Cannot benchmark: ${targetEng.name} is not installed locally.`);
      setTimeout(() => setErrorMessage(null), 5000);
      return;
    }
    setBenchmarkingEngineId(engineId);
    try {
      const res = await apiClient.post<any>(`/api/v1/idp/engines/${engineId}/benchmark`);
      setSuccessMessage(`Benchmark complete for ${targetEng?.name || engineId}! CER: ${res.cer}%, WER: ${res.wer}%`);
      setTimeout(() => setSuccessMessage(null), 4000);
      fetchEngines();
    } catch (err: any) {
      setErrorMessage(err.message || `Benchmark failed for ${engineId}`);
    } finally {
      setBenchmarkingEngineId(null);
    }
  };

  const handleSavePolicy = async () => {
    if (!isAdmin) return;
    try {
      setIsSavingPolicy(true);
      await apiClient.post("/api/v1/idp/engines/routing-policy", {
        default_engine: policy?.default_engine || "tesseract",
        fallback_engine: policy?.fallback_engine || "indra",
        rules: policy?.rules || [],
        yaml_content: yamlPolicy,
      });
      setSuccessMessage("Adaptive routing policy saved and activated for all incoming documents!");
      setTimeout(() => setSuccessMessage(null), 4000);
      fetchEngines();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to save routing policy");
    } finally {
      setIsSavingPolicy(false);
    }
  };

  const handlePresetChange = (key: string) => {
    setSelectedPresetKey(key);
    if (ROUTER_PRESETS[key]) {
      setProfileJsonText(ROUTER_PRESETS[key].json);
    }
  };

  const handleAskRouter = async () => {
    try {
      setIsAskingRouter(true);
      const res = await apiClient.post<any>("/api/v1/idp/engines/routing-policy/test", {
        profile_json: profileJsonText,
        profile_name: ROUTER_PRESETS[selectedPresetKey]?.label || "Custom Document Profile",
      });
      setRouterDecision(res);
    } catch (err: any) {
      setErrorMessage(err.message || "Router evaluation failed");
    } finally {
      setIsAskingRouter(false);
    }
  };

  const handleRollbackPolicy = async () => {
    if (!isAdmin) return;
    try {
      await apiClient.post("/api/v1/idp/engines/routing-policy/rollback", {});
      setSuccessMessage("Rolled back to previous OCR routing policy version!");
      setTimeout(() => setSuccessMessage(null), 3000);
      fetchEngines();
    } catch (err: any) {
      setErrorMessage(err.message || "Rollback failed");
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

  const totalEnginesCount = engines.length || 8;
  const enabledCount = engines.filter((e) => e.is_enabled).length;
  const runningInStackCount = engines.filter((e) => e.is_installed).length;

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-surface-50 dark:bg-surface-950">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-surface-200 dark:border-surface-800">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-surface-900 dark:text-surface-100 flex items-center gap-2">
              <Activity className="w-5 h-5 text-brand-600" />
              OCR Engine Orchestrator & Adaptive Routing
            </h1>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                Adaptive Hardware Profiling Active
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800">
                <ShieldCheck className="w-3 h-3 text-blue-600" />
                OPA Rego Enforced (Clearance L3)
              </span>
            </div>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 mt-1 max-w-4xl">
            Multi-engine document router dynamically tailored to your host laptop hardware. Throttles neural thread counts, adapts render DPI, and guarantees zero single-vendor dependency.
          </p>
        </div>

        <button
          onClick={fetchEngines}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-surface-700 dark:text-surface-300 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-lg hover:bg-surface-50 shadow-xs transition"
        >
          <RefreshCw className={clsx("w-3.5 h-3.5", isRefreshing && "animate-spin")} />
          <span>Refresh Hardware & Telemetry</span>
        </button>
      </div>

      {/* Notifications */}
      {errorMessage && (
        <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-red-500 hover:text-red-700 font-bold ml-2">✕</button>
        </div>
      )}

      {successMessage && (
        <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs text-emerald-800 dark:text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-2">✕</button>
        </div>
      )}

      {/* PROMINENT HOST LAPTOP HARDWARE SPECIFICATION & SPEED DECIDER BANNER */}
      {hardware && (
        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-xl p-5 shadow-sm border border-indigo-900/60 space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-3 border-b border-indigo-800/60">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-indigo-600/30 border border-indigo-400/40 rounded-lg text-indigo-300">
                <Cpu className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-bold tracking-wide text-white">
                    Host Hardware Specification & Adaptive Speed Decider
                  </h2>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    TIER: {hardware.tier || "LOW"}
                  </span>
                </div>
                <p className="text-xs text-indigo-200/80 mt-0.5">
                  {hardware.os_name} {hardware.os_version} • {hardware.cpu_model}
                </p>
              </div>
            </div>

            {/* Power / Speed Mode Selector */}
            <div className="flex items-center gap-2 bg-indigo-950/80 p-1 rounded-lg border border-indigo-800/80 text-xs">
              <span className="text-[11px] text-indigo-300 px-2 font-medium">Speed Profile:</span>
              {(["AUTO", "ECO", "PERFORMANCE"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setPowerMode(mode)}
                  className={clsx(
                    "px-2.5 py-1 rounded text-xs font-semibold transition",
                    powerMode === mode
                      ? "bg-indigo-600 text-white shadow-2xs"
                      : "text-indigo-300 hover:text-white"
                  )}
                >
                  {mode === "ECO" ? "Eco (Battery)" : mode === "PERFORMANCE" ? "High Perf" : "Auto"}
                </button>
              ))}
            </div>
          </div>

          {/* Real-time Hardware Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs font-mono">
            <div className="bg-white/5 rounded-lg p-2.5 border border-white/10">
              <span className="text-[10px] text-indigo-300 block mb-0.5">CPU CORES / LOAD</span>
              <span className="text-sm font-bold text-white">
                {hardware.physical_cores}C / {hardware.logical_cores}T
              </span>
              <span className="block text-[10px] text-indigo-300/70 mt-0.5">
                {hardware.cpu_load_percent}% Active Load
              </span>
            </div>

            <div className="bg-white/5 rounded-lg p-2.5 border border-white/10">
              <span className="text-[10px] text-indigo-300 block mb-0.5">AVAILABLE RAM</span>
              <span className="text-sm font-bold text-white">
                {hardware.available_ram_gb} GB
              </span>
              <span className="block text-[10px] text-indigo-300/70 mt-0.5">
                of {hardware.total_ram_gb} GB Total
              </span>
            </div>

            <div className="bg-white/5 rounded-lg p-2.5 border border-white/10">
              <span className="text-[10px] text-indigo-300 block mb-0.5">ACCELERATION / GPU</span>
              <span className="text-sm font-bold text-white truncate block" title={hardware.gpu_name || "CPU DirectML / ONNX"}>
                {hardware.has_gpu ? (hardware.gpu_name || "Discrete GPU") : "CPU DirectML / ONNX"}
              </span>
              <span className="block text-[10px] text-indigo-300/70 mt-0.5">
                {hardware.vram_free_gb ? `${hardware.vram_free_gb} GB VRAM free` : "ONNX DirectML"}
              </span>
            </div>

            <div className="bg-white/5 rounded-lg p-2.5 border border-white/10">
              <span className="text-[10px] text-indigo-300 block mb-0.5">POWER SOURCE</span>
              <span className="text-sm font-bold text-white flex items-center gap-1">
                <Battery className="w-3.5 h-3.5 text-amber-400" />
                {hardware.on_battery ? "Battery Power" : "AC Connected"}
              </span>
              <span className="block text-[10px] text-indigo-300/70 mt-0.5">
                {hardware.effective_mode} Policy Active
              </span>
            </div>

            <div className="bg-white/5 rounded-lg p-2.5 border border-white/10">
              <span className="text-[10px] text-indigo-300 block mb-0.5">ADAPTIVE ALLOCATION</span>
              <span className="text-sm font-bold text-emerald-400">
                {hardware.chosen_workers} Worker • {hardware.render_dpi} DPI
              </span>
              <span className="block text-[10px] text-indigo-300/70 mt-0.5">
                {hardware.chosen_threads} Threads/Task
              </span>
            </div>
          </div>

          {/* Warnings & Throttling Alert */}
          {hardware.warnings && hardware.warnings.length > 0 && (
            <div className="p-2.5 bg-amber-500/15 border border-amber-400/30 rounded-lg text-[11px] text-amber-200 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong>Adaptive Speed Optimization:</strong> {hardware.warnings.join(" • ")}. The router prioritizes lightweight vector and CPU ONNX engines to prevent system freezes.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Top 4 Metric KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Catalogued OCR Engines</span>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100 mt-1">{totalEnginesCount}</p>
        </div>
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Active in Tenant Policy</span>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-2xl font-bold text-brand-900 dark:text-brand-300">{enabledCount}</p>
            <span className="text-[11px] text-emerald-600 font-medium">enabled</span>
          </div>
        </div>
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Installed in Local Stack</span>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{runningInStackCount}</p>
            <span className="text-[11px] text-surface-400 font-mono">running</span>
          </div>
        </div>
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-surface-500 font-medium">Born-Digital Vector Share</span>
            <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">Preview, not enforced</span>
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">48%</p>
            <span className="text-[11px] text-surface-400 font-mono">synthetic benchmark</span>
          </div>
        </div>
      </div>

      {/* ENGINE CATALOGUE MATRIX WITH REAL-TIME SPEED ESTIMATION ON THIS SYSTEM */}
      <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs overflow-hidden">
        <div className="px-5 py-3.5 border-b border-surface-200 dark:border-surface-800 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-brand-600" />
              Engine Performance Matrix & Machine Speed Decider
            </h2>
            <p className="text-xs text-surface-500">
              Probed on host ({hardware?.physical_cores ?? "?"}-core CPU, {hardware?.available_ram_gb ?? "?"} GB free RAM, {hardware?.on_battery ? "Battery Saver" : "AC Connected"}).
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-50 dark:bg-surface-800/60 text-surface-500 font-semibold uppercase text-[10px] tracking-wider border-b border-surface-200 dark:border-surface-800">
              <tr>
                <th className="py-3 px-4 w-14">ACTIVE</th>
                <th className="py-3 px-4">ENGINE & ARCHITECTURE</th>
                <th className="py-3 px-3">EXECUTION DEVICE</th>
                <th className="py-3 px-3">RAM FOOTPRINT</th>
                <th className="py-3 px-3">SPEED (EST. / RUN)</th>
                <th className="py-3 px-3">ACCURACY (F1)</th>
                <th className="py-3 px-3">COST / PAGE</th>
                <th className="py-3 px-4">BEST SUITED FOR</th>
                <th className="py-3 px-4">ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100 dark:divide-surface-800 font-medium">
              {engines.map((eng) => {
                const metric = ENGINE_METRICS[eng.id] || {
                  arch: "OCR Engine",
                  deviceType: "CPU Only",
                  deviceBadgeColor: "bg-surface-100 text-surface-700",
                  ramFootprint: "~500 MB",
                  speedEstimate: "1.5 s",
                  f1Score: "92.0%",
                  bestFor: eng.description,
                };

                const hwStatus = hardware?.engine_devices?.[eng.id];
                const isSkippedDueToRam = hwStatus?.device === "SKIPPED";

                return (
                  <tr
                    key={eng.id}
                    className={clsx(
                      "hover:bg-surface-50/70 dark:hover:bg-surface-800/40 transition-colors",
                      !eng.is_enabled && "opacity-70 bg-surface-50/30"
                    )}
                  >
                    {/* ON / OFF Switch */}
                    <td className="py-3 px-4">
                      <label
                        className="relative inline-flex items-center cursor-pointer"
                        title={eng.is_enabled ? `Click to deactivate ${eng.name}` : `Click to activate ${eng.name}`}
                      >
                        <input
                          type="checkbox"
                          checked={eng.is_enabled}
                          disabled={!isAdmin}
                          onChange={() => handleToggle(eng.id, eng.is_enabled)}
                          className="sr-only peer"
                        />
                        <div className="w-8 h-4 bg-surface-200 peer-focus:outline-none rounded-full peer dark:bg-surface-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-surface-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all dark:border-surface-600 peer-checked:bg-brand-600"></div>
                      </label>
                    </td>

                    {/* Engine & Architecture */}
                    <td className="py-3 px-4">
                      <div>
                        <span className="font-bold text-surface-900 dark:text-surface-100 block">
                          {eng.name}
                        </span>
                        <span className="text-[11px] text-surface-400 font-mono">
                          {metric.arch} • {eng.model_revision}
                        </span>
                      </div>
                    </td>

                    {/* Execution Device Badge */}
                    <td className="py-3 px-3">
                      <span className={clsx("px-2 py-0.5 rounded text-[11px] font-medium border", metric.deviceBadgeColor)}>
                        {metric.deviceType}
                      </span>
                    </td>

                    {/* RAM Footprint */}
                    <td className="py-3 px-3 font-mono text-[11px] text-surface-700 dark:text-surface-300">
                      {metric.ramFootprint}
                    </td>

                    {/* Processing Speed */}
                    <td className="py-3 px-3 font-mono text-[11px]">
                      {isSkippedDueToRam ? (
                        <span className="text-amber-600 dark:text-amber-400 font-bold">
                          Throttled (RAM)
                        </span>
                      ) : eng.benchmark?.pages_per_sec ? (
                        <span className="font-bold text-emerald-600 dark:text-emerald-400" title="Measured benchmark">
                          {(1 / eng.benchmark.pages_per_sec).toFixed(2)} s (live)
                        </span>
                      ) : (
                        <span className="text-surface-600 dark:text-surface-400" title="Estimated hardware profile">
                          ~{metric.speedEstimate} (est)
                        </span>
                      )}
                    </td>

                    {/* Field Accuracy */}
                    <td className="py-3 px-3 font-mono text-[11px] text-surface-700 dark:text-surface-300">
                      {eng.benchmark?.field_f1 != null ? (
                        <span className="font-bold text-emerald-600 dark:text-emerald-400" title="Measured benchmark">
                          {(eng.benchmark.field_f1 * 100).toFixed(1)}% (live)
                        </span>
                      ) : (
                        <span className="text-surface-500" title="Pre-benchmark baseline profile">
                          {metric.f1Score} (profile)
                        </span>
                      )}
                    </td>

                    {/* Cost per Page */}
                    <td className="py-3 px-3 font-mono text-[11px] text-emerald-700 dark:text-emerald-300 font-bold">
                      $0.00
                    </td>

                    {/* Best Suited For */}
                    <td className="py-3 px-4 text-surface-600 dark:text-surface-400 text-xs max-w-xs">
                      {metric.bestFor}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => {
                            setTestingEngine(eng);
                            setTestResult(null);
                          }}
                          className="px-2 py-1 text-[11px] font-medium border border-surface-300 dark:border-surface-700 rounded hover:bg-surface-100 dark:hover:bg-surface-800 transition"
                        >
                          Test
                        </button>
                        <button
                          onClick={() => handleRunBenchmark(eng.id)}
                          disabled={!isAdmin || benchmarkingEngineId === eng.id}
                          className="px-2 py-1 text-[11px] font-medium bg-brand-50 text-brand-700 rounded hover:bg-brand-100 disabled:opacity-50 transition"
                        >
                          {benchmarkingEngineId === eng.id ? "Benchmarking..." : "Benchmark"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* BOTTOM SECTION: ROUTING POLICY & SIMULATOR HUB */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
        {/* Left Column: Adaptive Routing Policy Hub */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-surface-200 dark:border-surface-800 mb-3">
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100 flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-brand-700" />
                Adaptive OCR Routing Policy
              </h2>
              <p className="text-xs text-surface-500">Evaluated on every incoming invoice before processing</p>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center bg-surface-100 dark:bg-surface-800 p-0.5 rounded border border-surface-200 dark:border-surface-700 text-xs">
                <button
                  onClick={() => setPolicyTab("visual")}
                  className={clsx(
                    "px-2 py-1 rounded font-semibold text-[11px] transition",
                    policyTab === "visual"
                      ? "bg-white dark:bg-surface-700 text-brand-900 dark:text-white shadow-2xs"
                      : "text-surface-600 dark:text-surface-300"
                  )}
                >
                  Visual Rules
                </button>
                <button
                  onClick={() => setPolicyTab("yaml")}
                  className={clsx(
                    "px-2 py-1 rounded font-semibold text-[11px] transition",
                    policyTab === "yaml"
                      ? "bg-white dark:bg-surface-700 text-brand-900 dark:text-white shadow-2xs"
                      : "text-surface-600 dark:text-surface-300"
                  )}
                >
                  YAML Editor
                </button>
              </div>

              {policyHistory.length > 0 && (
                <button
                  onClick={handleRollbackPolicy}
                  disabled={!isAdmin}
                  className="flex items-center gap-1 px-2.5 py-1.5 text-xs text-surface-600 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-800 rounded border border-surface-200 dark:border-surface-700 transition"
                  title="Rollback to previous saved policy"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Rollback
                </button>
              )}

              <button
                onClick={handleSavePolicy}
                disabled={!isAdmin || isSavingPolicy}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-brand-900 hover:bg-brand-950 rounded-md shadow-xs transition"
              >
                <Save className="w-3.5 h-3.5" />
                {isSavingPolicy ? "Saving..." : "Save Policy"}
              </button>
            </div>
          </div>

          {policyTab === "visual" ? (
            /* Visual Rule Builder Cards */
            <div className="space-y-3 flex-1 overflow-y-auto pr-1">
              <div className="p-3 bg-surface-50 dark:bg-surface-800/40 rounded-lg border border-surface-200 dark:border-surface-800 flex items-start gap-3">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-200 flex items-center justify-center font-bold text-xs shrink-0">
                  1
                </span>
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-surface-900 dark:text-surface-100">Born-Digital PDF Stream</span>
                    <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 font-mono text-[10px]">
                      Use PyMuPDF Vector Layer
                    </span>
                  </div>
                  <p className="text-surface-500 text-[11px] mt-0.5">
                    When text layer coverage &ge; 85%, extract vector glyphs directly without running optical inference. Instant 0.08s speed, zero optical error.
                  </p>
                </div>
              </div>

              <div className="p-3 bg-surface-50 dark:bg-surface-800/40 rounded-lg border border-surface-200 dark:border-surface-800 flex items-start gap-3">
                <span className="w-6 h-6 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/60 dark:text-purple-200 flex items-center justify-center font-bold text-xs shrink-0">
                  2
                </span>
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-surface-900 dark:text-surface-100">Indic & Devanagari Scripts</span>
                    <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 font-mono text-[10px]">
                      Use Indra OCR Transformer
                    </span>
                  </div>
                  <p className="text-surface-500 text-[11px] mt-0.5">
                    When document language is Hindi, Bengali, Tamil, or Cyrillic, route to Indra CPU ONNX transformer. Fast 0.65s inference without GPU dependency.
                  </p>
                </div>
              </div>

              <div className="p-3 bg-surface-50 dark:bg-surface-800/40 rounded-lg border border-surface-200 dark:border-surface-800 flex items-start gap-3">
                <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-200 flex items-center justify-center font-bold text-xs shrink-0">
                  3
                </span>
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-surface-900 dark:text-surface-100">Scanned Invoices & Photos</span>
                    <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 font-mono text-[10px]">
                      Use Tesseract 5 + OpenCV
                    </span>
                  </div>
                  <p className="text-surface-500 text-[11px] mt-0.5">
                    Standard scanned invoices pass through OpenCV deskew, contrast-limited adaptive histogram equalization (CLAHE), and multi-threaded Tesseract 5.
                  </p>
                </div>
              </div>

              <div className="p-3 bg-surface-50 dark:bg-surface-800/40 rounded-lg border border-surface-200 dark:border-surface-800 flex items-start gap-3">
                <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-200 flex items-center justify-center font-bold text-xs shrink-0">
                  4
                </span>
                <div className="flex-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-surface-900 dark:text-surface-100">Complex Zero-Shot Reasoning</span>
                    <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 font-mono text-[10px]">
                      Use Ollama Vision LLM
                    </span>
                  </div>
                  <p className="text-surface-500 text-[11px] mt-0.5">
                    For handwritten purchase orders or documents with complex non-standard layouts, route to local offline multimodal vision model.
                  </p>
                </div>
              </div>

              <div className="p-2.5 bg-brand-50 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-800 rounded-lg text-[11px] text-brand-900 dark:text-brand-200 flex items-center gap-2">
                <Check className="w-4 h-4 text-brand-600 shrink-0" />
                <span>
                  <strong>Failover Cascade:</strong> Selected Engine &rarr; Indra/Tesseract Failover &rarr; Human Review Workbench.
                </span>
              </div>
            </div>
          ) : (
            /* YAML Editor */
            <div className="flex-1 flex flex-col">
              <textarea
                value={yamlPolicy}
                onChange={(e) => setYamlPolicy(e.target.value)}
                rows={16}
                className="w-full flex-1 p-3 font-mono text-[11px] leading-relaxed bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100 border border-surface-200 dark:border-surface-800 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
                spellCheck={false}
              />
            </div>
          )}
        </div>

        {/* Right Column: Test the Adaptive Router (Simulator) */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs flex flex-col">
          <div className="pb-3 border-b border-surface-200 dark:border-surface-800 mb-3">
            <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-brand-600" />
              Test the Adaptive Router (Simulator)
            </h2>
            <p className="text-xs text-surface-500">
              Simulate document routing decisions evaluated against this machine's CPU & memory state
            </p>
          </div>

          <div className="space-y-3 flex-1 flex flex-col">
            {/* Document Profile Preset Selector */}
            <div>
              <label className="block text-xs font-semibold text-surface-700 dark:text-surface-300 mb-1">
                Document archetype preset:
              </label>
              <select
                value={selectedPresetKey}
                onChange={(e) => handlePresetChange(e.target.value)}
                className="w-full text-xs bg-surface-50 dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded-md p-2 font-medium"
              >
                {Object.entries(ROUTER_PRESETS).map(([k, p]) => (
                  <option key={k} value={k}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Profile JSON Editor */}
            <div className="flex-1 flex flex-col">
              <label className="block text-xs font-medium text-surface-500 mb-1">
                Document parameters payload:
              </label>
              <textarea
                value={profileJsonText}
                onChange={(e) => setProfileJsonText(e.target.value)}
                rows={6}
                className="w-full p-2.5 font-mono text-[11px] leading-relaxed bg-surface-50 dark:bg-surface-950 text-surface-800 dark:text-surface-200 border border-surface-200 dark:border-surface-800 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
                spellCheck={false}
              />
            </div>

            {/* Ask the router Button */}
            <button
              onClick={handleAskRouter}
              disabled={isAskingRouter}
              className="w-full py-2.5 bg-brand-900 hover:bg-brand-950 text-white rounded-md text-xs font-semibold shadow-xs flex items-center justify-center gap-1.5 transition"
            >
              <Sparkles className="w-3.5 h-3.5 text-brand-300" />
              <span>{isAskingRouter ? "Evaluating against host specifications..." : "✦ Evaluate Routing Decision"}</span>
            </button>

            {/* Decision Rationale Container */}
            <div className="p-3 bg-surface-50 dark:bg-surface-950 border border-surface-200 dark:border-surface-800 rounded-lg text-xs min-h-[90px] flex flex-col justify-center">
              {routerDecision ? (
                <div className="space-y-2 animate-fadeIn">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-surface-900 dark:text-surface-100 text-sm">
                        Selected: {routerDecision.engine_name}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-brand-100 dark:bg-brand-950 text-brand-800 dark:text-brand-300">
                        {routerDecision.selected_engine}
                      </span>
                    </div>
                    <span className="font-mono text-xs text-emerald-600 font-bold">
                      Confidence: {routerDecision.confidence_estimate}%
                    </span>
                  </div>

                  <p className="text-surface-700 dark:text-surface-300 text-xs">
                    {routerDecision.decision_reason}
                  </p>

                  <div className="pt-2 border-t border-surface-200 dark:border-surface-800 flex flex-wrap items-center justify-between gap-2 text-[11px] text-surface-500 font-mono">
                    <span>Latency on this CPU: <strong className="text-surface-800 dark:text-surface-200">{routerDecision.estimated_p50}</strong></span>
                    <span>Cost: <strong className="text-emerald-700 dark:text-emerald-300">{routerDecision.estimated_cost}</strong></span>
                    <span>Failover Cascade: <strong className="text-surface-700 dark:text-surface-300">{routerDecision.fallback_chain?.join(" &rarr; ")}</strong></span>
                  </div>
                </div>
              ) : (
                <div className="text-center text-surface-400 py-3">
                  <Sparkles className="w-5 h-5 mx-auto mb-1 text-surface-300" />
                  <span>Click "Evaluate Routing Decision" to simulate execution on your system.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Engine Test Modal */}
      {testingEngine && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-6 max-w-lg w-full space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-surface-200 dark:border-surface-800">
              <h3 className="font-bold text-sm text-surface-900 dark:text-surface-100">
                Execute Test: {testingEngine.name}
              </h3>
              <button
                onClick={() => setTestingEngine(null)}
                className="text-surface-400 hover:text-surface-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-surface-700 dark:text-surface-300 font-medium mb-1">
                  Benchmark Sample:
                </label>
                <select
                  value={testSampleId}
                  onChange={(e) => setTestSampleId(e.target.value)}
                  className="w-full p-2 border border-surface-300 dark:border-surface-700 rounded bg-surface-50 dark:bg-surface-800 font-mono"
                >
                  <option value="clean_invoice">inv_000_clean.png (Clear Print Invoice)</option>
                  <option value="shadowed_receipt">inv_001_shadowed.png (Phone Photo with Shadow)</option>
                  <option value="skewed_scan">inv_002_skewed.png (Rotated 4° Scan)</option>
                </select>
              </div>

              <div>
                <label className="block text-surface-700 dark:text-surface-300 font-medium mb-1">
                  Or Upload Document File:
                </label>
                <input
                  type="file"
                  accept="image/*,application/pdf"
                  onChange={(e) => setTestFile(e.target.files?.[0] || null)}
                  className="w-full p-2 border border-surface-300 dark:border-surface-700 rounded text-xs"
                />
              </div>

              {testResult && (
                <div className="p-3 bg-surface-50 dark:bg-surface-950 border border-surface-200 dark:border-surface-800 rounded font-mono text-[11px] space-y-1">
                  <div className="flex justify-between font-bold text-surface-900 dark:text-surface-100">
                    <span>Latency: {testResult.elapsed_ms} ms</span>
                    <span>Confidence: {testResult.confidence?.toFixed(1)}%</span>
                  </div>
                  <div className="max-h-32 overflow-auto text-surface-600 dark:text-surface-400 text-[10px] mt-1 whitespace-pre-wrap">
                    {testResult.raw_text_preview || "No text extracted"}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-surface-200 dark:border-surface-800">
              <button
                onClick={() => setTestingEngine(null)}
                className="px-3 py-1.5 border border-surface-300 rounded text-xs text-surface-700 hover:bg-surface-50"
              >
                Close
              </button>
              <button
                onClick={handleRunTest}
                disabled={isTesting}
                className="px-4 py-1.5 bg-brand-900 hover:bg-brand-950 text-white font-semibold text-xs rounded shadow-xs"
              >
                {isTesting ? "Executing..." : "Run Test"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OcrEnginesControlCenterView;
