import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  Cpu,
  RefreshCw,
  RotateCcw,
  FileText,
  Sparkles,
  Layers,
  BookOpen,
  Type,
  Sun,
  Eye,
  Table as TableIcon,
  LayoutGrid,
  Save,
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

const DEFAULT_YAML_POLICY = `# routing-policy v7 - the router reads this before choosing an engine
defaults:
  confidence_threshold: 0.85   # below this the Critic switches engine
  field_threshold: 0.80        # any key field below this -> human review
  max_engine_attempts: 3
rules:
  - when: file.type in [xlsx, xls, csv]        use: sheet
  - when: file.type in [edi, xml, x12, delfor]  use: edi
  - when: pdf.text_coverage >= 0.9             use: native
  - when: language in [hi, bn, ru, el]         use: indra
  - when: complexity_score <= 40               use: tesseract
  - when: complexity_score <= 75               use: paddle
  - when: complexity_score > 75                use: vision
  - when: handwriting or novel_layout          use: vision
fallback_order: [native, indra, tesseract, paddle, vision]
pin:
  - sender: "*@ups.com"          engine: native   # consolidated bills are digital
  - must_use_llm: True           engine: vision   # forced from the upload screen
cost_guardrail:
  max_cost_per_page_usd: 0.15
  vision_llm_share_cap: 0.10`;

const ROUTER_PRESETS: Record<string, { label: string; json: string }> = {
  po_skewed: {
    label: "Phone photo of a customer PO, skewed, 150 dpi",
    json: JSON.stringify(
      {
        photo: true,
        dpi: 150,
        skewDeg: 4,
        pages: 1,
        language: "en",
        sender: "buyer@ridgeviewinteriors.example",
      },
      null,
      2
    ),
  },
  digital_pdf: {
    label: "Born-digital vendor invoice (PDF vector text layer)",
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
  sbc_tamilnadu: {
    label: "Tamil Nadu cash bill / rental invoice (SBC-0590)",
    json: JSON.stringify(
      {
        file_type: "pdf",
        dpi: 300,
        is_gst_invoice: true,
        state_code: "33",
        language: "tam+eng",
        sender: "bcitvir@gmail.com",
      },
      null,
      2
    ),
  },
  hindi_devanagari: {
    label: "Hindi / Devanagari clean print invoice",
    json: JSON.stringify(
      {
        file_type: "pdf",
        dpi: 300,
        language: "hin",
        complexity_score: 55,
        clean_print: true,
      },
      null,
      2
    ),
  },
  receipt_thermal: {
    label: "Degraded thermal retail receipt (low contrast, wrinkled)",
    json: JSON.stringify(
      {
        photo: true,
        dpi: 180,
        skewDeg: 6,
        contrast_ratio: 0.45,
        document_type: "receipt",
      },
      null,
      2
    ),
  },
};

const ENGINE_METADATA_EXT: Record<
  string,
  {
    typeLabel: string;
    typeColor: string;
    deployment: string;
    accuracyLabel: string;
    costPerPage: string;
    p95: string;
    bestFor: string;
    trafficShare: number;
    buildStatus: string;
  }
> = {
  pymupdf: {
    typeLabel: "Parser",
    typeColor: "bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-800",
    deployment: "Embedded",
    accuracyLabel: "99% (digital)",
    costPerPage: "$0",
    p95: "0.3 s",
    bestFor: "Born-digital PDFs",
    trafficShare: 41,
    buildStatus: "Runs live",
  },
  tesseract: {
    typeLabel: "Open source",
    typeColor: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
    deployment: "On-prem container",
    accuracyLabel: "88–93% / 78–88%",
    costPerPage: "~$0.002",
    p95: "4.5 s",
    bestFor: "Cost floor, sovereign, fallback",
    trafficShare: 24,
    buildStatus: "Runs live",
  },
  indra: {
    typeLabel: "Neural / ONNX",
    typeColor: "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-800",
    deployment: "CPU Only",
    accuracyLabel: "94–98% / 91–95%",
    costPerPage: "$0",
    p95: "0.8 s",
    bestFor: "Latin, Devanagari, Bengali, Cyrillic, Greek, Chinese",
    trafficShare: 18,
    buildStatus: "Runs live",
  },
  paddleocr: {
    typeLabel: "Deep Learning",
    typeColor: "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800",
    deployment: "CPU / GPU",
    accuracyLabel: "91–96% / 85–92%",
    costPerPage: "~$0.003",
    p95: "2.1 s",
    bestFor: "Angle classification, multilingual",
    trafficShare: 7,
    buildStatus: "Standby",
  },
  doctr: {
    typeLabel: "Neural / DBNet",
    typeColor: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800",
    deployment: "CPU / GPU",
    accuracyLabel: "92–97% / 88–94%",
    costPerPage: "~$0.004",
    p95: "2.8 s",
    bestFor: "Table parsing, two-stage detection",
    trafficShare: 5,
    buildStatus: "Standby",
  },
  easyocr: {
    typeLabel: "PyTorch / CRAFT",
    typeColor: "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800",
    deployment: "CPU / GPU",
    accuracyLabel: "86–92% / 80–87%",
    costPerPage: "~$0.003",
    p95: "3.2 s",
    bestFor: "80+ languages, natural scene text",
    trafficShare: 3,
    buildStatus: "Standby",
  },
  surya: {
    typeLabel: "Vision Transformer",
    typeColor: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800",
    deployment: "CPU / GPU",
    accuracyLabel: "93–97% / 89–95%",
    costPerPage: "~$0.005",
    p95: "3.5 s",
    bestFor: "Reading order, line detection, 90+ langs",
    trafficShare: 1,
    buildStatus: "Standby",
  },
  ollama: {
    typeLabel: "Vision LLM",
    typeColor: "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-800",
    deployment: "Local daemon",
    accuracyLabel: "95–99% / 93–98%",
    costPerPage: "$0 (Local)",
    p95: "4.8 s",
    bestFor: "Visual QA, complex reasoning, zero-shot JSON",
    trafficShare: 1,
    buildStatus: "Connector",
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

  // View Switcher: "catalogue" (Table view matching user reference) vs "cards" (Deep engine cards)
  const [viewMode, setViewMode] = useState<"catalogue" | "cards">("catalogue");

  // Routing Policy YAML editor state
  const [yamlPolicy, setYamlPolicy] = useState<string>(DEFAULT_YAML_POLICY);
  const [isSavingPolicy, setIsSavingPolicy] = useState(false);

  // Ask the router simulator state
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

  // Benchmark Run State
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
          `${targetEng.name} is now enabled in tenant routing policy. (Note: Engine package is not yet installed locally; processing will auto-fallback to available engines until installed).`
        );
      } else {
        setSuccessMessage(`Engine ${targetEng?.name || engineId} is now ${nextState ? "enabled" : "disabled"}`);
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
      setErrorMessage(`Cannot run benchmark: ${targetEng.name} is not installed locally (${targetEng.status}).`);
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
      setSuccessMessage("Routing policy saved and activated for all incoming documents!");
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
        return <FileText className="w-4 h-4 text-sky-500" />;
      case "Sparkles":
        return <Sparkles className="w-4 h-4 text-purple-500" />;
      case "Layers":
        return <Layers className="w-4 h-4 text-indigo-500" />;
      case "BookOpen":
        return <BookOpen className="w-4 h-4 text-amber-500" />;
      case "Type":
        return <Type className="w-4 h-4 text-emerald-500" />;
      case "Sun":
        return <Sun className="w-4 h-4 text-orange-500" />;
      case "Eye":
        return <Eye className="w-4 h-4 text-teal-500" />;
      case "Cpu":
      default:
        return <Cpu className="w-4 h-4 text-brand-500" />;
    }
  };

  // Top metric counts matching reference screenshot 1
  const totalEnginesCount = engines.length || 8;
  const enabledCount = engines.filter((e) => e.is_enabled).length;
  const runningInStackCount = engines.filter((e) => e.is_installed).length;
  const bornDigitalShare = "48%";

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-surface-50 dark:bg-surface-950">
      {/* Top Header matching Screenshot 1 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-surface-200 dark:border-surface-800">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
              OCR Router
            </h1>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                Orchestrator healthy
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                SAP ECC 6.0 EHP8 · PRD client 100 (simulated)
              </span>
            </div>
          </div>
          <p className="text-xs text-surface-500 dark:text-surface-400 mt-1 max-w-4xl">
            The router profiles each document and picks an engine under the routing policy. If confidence falls below threshold the weak pages are re-read by the next engine in the chain, so no single OCR vendor is load-bearing.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* View Toggle */}
          <div className="flex items-center bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-lg p-0.5 shadow-xs">
            <button
              onClick={() => setViewMode("catalogue")}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition",
                viewMode === "catalogue"
                  ? "bg-brand-900 text-white shadow-xs"
                  : "text-surface-600 hover:text-surface-900 dark:text-surface-300"
              )}
            >
              <TableIcon className="w-3.5 h-3.5" />
              Catalogue Table
            </button>
            <button
              onClick={() => setViewMode("cards")}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md transition",
                viewMode === "cards"
                  ? "bg-brand-900 text-white shadow-xs"
                  : "text-surface-600 hover:text-surface-900 dark:text-surface-300"
              )}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              Engine Details
            </button>
          </div>

          <button
            onClick={fetchEngines}
            disabled={isRefreshing}
            title="Refresh engines status"
            className="p-2 text-surface-600 dark:text-surface-300 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-lg hover:bg-surface-50 shadow-xs transition"
          >
            <RefreshCw className={clsx("w-3.5 h-3.5", isRefreshing && "animate-spin")} />
          </button>
        </div>
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

      {/* 4 Top Stat Cards Matching Screenshot 1 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Engines in the catalogue</span>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100 mt-1">{totalEnginesCount}</p>
        </div>
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Enabled</span>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{enabledCount}</p>
            <span className="text-[11px] text-emerald-600 font-medium">active routing</span>
          </div>
        </div>
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Running in this stack</span>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{runningInStackCount}</p>
            <span className="text-[11px] text-surface-400 font-mono">installed</span>
          </div>
        </div>
        <div className="p-4 bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs">
          <span className="text-xs text-surface-500 font-medium">Born-digital, no OCR</span>
          <div className="flex items-baseline gap-2 mt-1">
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{bornDigitalShare}</p>
            <span className="text-[11px] text-surface-400 font-mono">synthetic</span>
          </div>
        </div>
      </div>

      {/* VIEW 1: ENGINE CATALOGUE TABLE MATCHING SCREENSHOT 1 */}
      {viewMode === "catalogue" ? (
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl shadow-xs overflow-hidden">
          <div className="px-5 py-3.5 border-b border-surface-200 dark:border-surface-800 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                Engine catalogue
              </h2>
              <p className="text-xs text-surface-500">
                Open-source and proprietary engines behind one adapter interface
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-50 dark:bg-surface-800/60 text-surface-500 font-semibold uppercase text-[10px] tracking-wider border-b border-surface-200 dark:border-surface-800">
                <tr>
                  <th className="py-3 px-4 w-14">ON</th>
                  <th className="py-3 px-4">ENGINE</th>
                  <th className="py-3 px-3">TYPE</th>
                  <th className="py-3 px-3">DEPLOYMENT</th>
                  <th className="py-3 px-3">ACCURACY (HEADER / LINE)</th>
                  <th className="py-3 px-3">COST / PAGE</th>
                  <th className="py-3 px-3">P95</th>
                  <th className="py-3 px-4">BEST FOR</th>
                  <th className="py-3 px-4 w-32">SHARE · 30 D</th>
                  <th className="py-3 px-4">IN THIS BUILD</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100 dark:divide-surface-800 font-medium">
                {engines.map((eng) => {
                  const meta = ENGINE_METADATA_EXT[eng.id] || {
                    typeLabel: "Open source",
                    typeColor: "bg-surface-100 text-surface-700",
                    deployment: "Container",
                    accuracyLabel: "90-95%",
                    costPerPage: "$0",
                    p95: "1.5 s",
                    bestFor: eng.description,
                    trafficShare: 5,
                    buildStatus: eng.is_installed ? "Runs live" : "Standby",
                  };

                  return (
                    <tr
                      key={eng.id}
                      className={clsx(
                        "hover:bg-surface-50/70 dark:hover:bg-surface-800/40 transition-colors",
                        !eng.is_enabled && "opacity-75"
                      )}
                    >
                      {/* ON / OFF Switch */}
                      <td className="py-3 px-4">
                        <label
                          className="relative inline-flex items-center cursor-pointer"
                          title={eng.is_enabled ? `Click to turn off ${eng.name}` : `Click to turn on ${eng.name}`}
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

                      {/* Engine Name */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          {renderIcon(eng.icon)}
                          <div>
                            <span className="font-semibold text-surface-900 dark:text-surface-100">
                              {eng.id === "pymupdf"
                                ? "Native PDF text layer"
                                : eng.id === "tesseract"
                                ? "Tesseract 5 + LayoutLMv3"
                                : eng.name}
                            </span>
                            <span className="block text-[11px] text-surface-400 font-mono">
                              {eng.model_revision}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Type Badge */}
                      <td className="py-3 px-3">
                        <span className={clsx("px-2 py-0.5 rounded text-[11px] font-medium border", meta.typeColor)}>
                          {meta.typeLabel}
                        </span>
                      </td>

                      {/* Deployment */}
                      <td className="py-3 px-3 text-surface-600 dark:text-surface-400 font-mono text-[11px]">
                        {meta.deployment}
                      </td>

                      {/* Accuracy */}
                      <td className="py-3 px-3 font-mono text-[11px] text-surface-700 dark:text-surface-300">
                        {meta.accuracyLabel}
                      </td>

                      {/* Cost / Page */}
                      <td className="py-3 px-3 font-mono text-[11px] text-surface-800 dark:text-surface-200">
                        {meta.costPerPage}
                      </td>

                      {/* P95 Latency */}
                      <td className="py-3 px-3 font-mono text-[11px] text-surface-500">
                        {meta.p95}
                      </td>

                      {/* Best For */}
                      <td className="py-3 px-4 text-surface-600 dark:text-surface-400 text-xs max-w-xs">
                        {meta.bestFor}
                      </td>

                      {/* Share 30 D */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-surface-100 dark:bg-surface-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className="bg-brand-600 h-1.5 rounded-full"
                              style={{ width: `${meta.trafficShare}%` }}
                            />
                          </div>
                          <span className="font-mono text-[11px] text-surface-500">{meta.trafficShare}%</span>
                        </div>
                      </td>

                      {/* In This Build */}
                      <td className="py-3 px-4">
                        <span
                          className={clsx(
                            "px-2 py-0.5 rounded text-[11px] font-medium",
                            eng.is_installed
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300"
                              : "bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400"
                          )}
                        >
                          {eng.is_installed ? "Runs live" : meta.buildStatus}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* VIEW 2: DEEP CARDS & HARDWARE PROFILE */
        <div className="space-y-6">
          {hardware && (
            <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-surface-100 dark:border-surface-800">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 rounded-lg text-indigo-600">
                    <Cpu className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                      Host Hardware & Adaptive Resource Profile
                    </h2>
                    <p className="text-xs text-surface-500">
                      {hardware.os_name} • {hardware.cpu_model} ({hardware.physical_cores}C / {hardware.logical_cores}T) • Tier: {hardware.tier}
                    </p>
                  </div>
                </div>
                <div className="text-right text-xs font-mono">
                  <span className="text-surface-400 block text-[10px]">Active Allocation</span>
                  <span className="font-semibold text-surface-800 dark:text-surface-200">
                    {hardware.chosen_workers} workers / {hardware.render_dpi} DPI
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Engine Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {engines.map((eng) => (
              <div
                key={eng.id}
                className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-4 shadow-xs flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {renderIcon(eng.icon)}
                      <h3 className="font-bold text-xs text-surface-900 dark:text-surface-100">{eng.name}</h3>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={eng.is_enabled}
                        disabled={!isAdmin}
                        onChange={() => handleToggle(eng.id, eng.is_enabled)}
                        className="sr-only peer"
                      />
                      <div className="w-7 h-4 bg-surface-200 peer-focus:outline-none rounded-full peer dark:bg-surface-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-brand-600"></div>
                    </label>
                  </div>
                  <p className="text-xs text-surface-500 line-clamp-2 mb-3">{eng.description}</p>
                </div>
                <div className="flex items-center gap-2 pt-3 border-t border-surface-100 dark:border-surface-800">
                  <button
                    onClick={() => {
                      setTestingEngine(eng);
                      setTestResult(null);
                    }}
                    className="flex-1 py-1 text-xs font-medium border border-surface-300 dark:border-surface-700 rounded hover:bg-surface-50"
                  >
                    Test
                  </button>
                  <button
                    onClick={() => handleRunBenchmark(eng.id)}
                    disabled={!isAdmin || benchmarkingEngineId === eng.id}
                    className="flex-1 py-1 text-xs font-medium bg-brand-50 text-brand-700 rounded hover:bg-brand-100 disabled:opacity-50"
                  >
                    Benchmark
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* BOTTOM SECTION: 2-COLUMN SECTION MATCHING SCREENSHOT 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
        {/* Left Column: Routing Policy YAML Editor */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-surface-200 dark:border-surface-800 mb-3">
            <div>
              <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                Routing policy
              </h2>
              <p className="text-xs text-surface-500">Read before every routing decision</p>
            </div>
            <div className="flex items-center gap-2">
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
                {isSavingPolicy ? "Saving..." : "Save policy"}
              </button>
            </div>
          </div>

          <div className="flex-1 flex flex-col">
            <textarea
              value={yamlPolicy}
              onChange={(e) => setYamlPolicy(e.target.value)}
              rows={18}
              className="w-full flex-1 p-3 font-mono text-[11px] leading-relaxed bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-surface-100 border border-surface-200 dark:border-surface-800 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
              spellCheck={false}
            />
          </div>
        </div>

        {/* Right Column: Test the router Sandbox */}
        <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl p-5 shadow-xs flex flex-col">
          <div className="pb-3 border-b border-surface-200 dark:border-surface-800 mb-3">
            <h2 className="text-sm font-bold text-surface-900 dark:text-surface-100">
              Test the router
            </h2>
            <p className="text-xs text-surface-500">Describe a document; the router picks an engine</p>
          </div>

          <div className="space-y-3 flex-1 flex flex-col">
            {/* Document Profile Preset Selector */}
            <div>
              <label className="block text-xs font-semibold text-surface-700 dark:text-surface-300 mb-1">
                Document profile
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
                Profile sent to the router
              </label>
              <textarea
                value={profileJsonText}
                onChange={(e) => setProfileJsonText(e.target.value)}
                rows={7}
                className="w-full p-2.5 font-mono text-[11px] leading-relaxed bg-surface-50 dark:bg-surface-950 text-surface-800 dark:text-surface-200 border border-surface-200 dark:border-surface-800 rounded-lg focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
                spellCheck={false}
              />
            </div>

            {/* Ask the router Button */}
            <button
              onClick={handleAskRouter}
              disabled={isAskingRouter}
              className="w-full py-2 bg-brand-900 hover:bg-brand-950 text-white rounded-md text-xs font-semibold shadow-xs flex items-center justify-center gap-1.5 transition"
            >
              <Sparkles className="w-3.5 h-3.5 text-brand-300" />
              <span>{isAskingRouter ? "Evaluating Policy..." : "Ask the router"}</span>
            </button>

            {/* Decision Rationale Container */}
            <div className="p-3 bg-surface-50 dark:bg-surface-950 border border-surface-200 dark:border-surface-800 rounded-lg text-xs min-h-[90px] flex flex-col justify-center">
              {routerDecision ? (
                <div className="space-y-1.5 animate-fadeIn">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-surface-900 dark:text-surface-100">
                        Primary: {routerDecision.engine_name}
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-brand-100 dark:bg-brand-950 text-brand-800 dark:text-brand-300">
                        {routerDecision.selected_engine}
                      </span>
                    </div>
                    <span className="font-mono text-[11px] text-emerald-600 font-bold">
                      Est. Conf: {routerDecision.confidence_estimate}%
                    </span>
                  </div>

                  <p className="text-surface-600 dark:text-surface-400 text-[11px]">
                    {routerDecision.decision_reason}
                  </p>

                  <div className="flex items-center gap-3 pt-1 text-[10px] text-surface-400 font-mono border-t border-surface-200/50 dark:border-surface-800/50">
                    <span>p50: {routerDecision.estimated_p50}</span>
                    <span>Cost: {routerDecision.estimated_cost}</span>
                    <span>Cascade: {routerDecision.fallback_chain?.join(" → ")}</span>
                  </div>
                </div>
              ) : (
                <p className="text-surface-400 text-center italic text-xs">
                  The decision and rationale appear here.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Test Engine Modal */}
      {testingEngine && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-xl w-full max-w-xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-800">
              <h3 className="text-sm font-bold text-surface-900 dark:text-surface-100">
                Test Engine: {testingEngine.name}
              </h3>
              <button onClick={() => setTestingEngine(null)} className="text-surface-400 hover:text-surface-600">✕</button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto flex-1 text-xs">
              <div>
                <label className="block font-medium mb-1">Select Bundled Sample Document</label>
                <select
                  value={testSampleId}
                  onChange={(e) => {
                    setTestSampleId(e.target.value);
                    setTestFile(null);
                  }}
                  className="w-full bg-surface-50 dark:bg-surface-800 border border-surface-300 dark:border-surface-700 rounded p-2"
                >
                  <option value="clean_invoice">Clean Enterprise Invoice (300 DPI)</option>
                  <option value="degraded_invoice">Degraded Invoice (Skew + Blur)</option>
                  <option value="receipt">Thermal Retail Receipt</option>
                  <option value="contract">Legal Agreement / Contract</option>
                </select>
              </div>
              <button
                onClick={handleRunTest}
                disabled={isTesting}
                className="w-full py-2 bg-brand-900 text-white rounded font-semibold"
              >
                {isTesting ? "Executing OCR..." : "Run OCR Test"}
              </button>
              {testResult && (
                <div className="p-3 bg-surface-50 dark:bg-surface-950 border rounded font-mono text-[11px] space-y-1">
                  <div className="flex justify-between font-bold">
                    <span>Processed in: {testResult.processing_time_ms} ms</span>
                    <span>Words: {testResult.total_words}</span>
                  </div>
                  <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap text-surface-700 dark:text-surface-300">
                    {testResult.full_text}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
