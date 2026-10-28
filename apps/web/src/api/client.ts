/**
 * Typed API Client for Elixir Enterprise Information Management.
 * Connected to live backend at /api/v1/*.
 */

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  first_name?: string | null;
  last_name?: string | null;
  roles: string[];
  department?: string | null;
  clearance_level: number;
  tenant_id: string;
}

export interface DirectTokenPayload {
  username: string;
  password: string;
  tenant_id?: string;
}

export interface StepUpPayload {
  otp_code: string;
  reason?: string;
}

export interface AuditEventItem {
  id: string;
  tenant_id: string;
  sequence_number: number;
  prev_hash: string;
  current_hash: string;
  timestamp: string;
  actor_id: string;
  actor_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  outcome: string;
  reason?: string | null;
  ip_address?: string | null;
  correlation_id: string;
  payload: Record<string, unknown>;
}

export interface AuditListResponse {
  items: AuditEventItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChainViolation {
  sequence_number: number;
  tenant_id: string;
  event_id: string;
  violation_type: string;
  details: string;
}

export interface AuditVerificationSummary {
  is_valid: boolean;
  total_events: number;
  tenants_checked: number;
  violations: ChainViolation[];
}

export interface SystemInfo {
  name: string;
  shortName: string;
  version: string;
  buildVersion: string;
  apiVersion: string;
  environment: string;
  uptimeSeconds: number;
  activeModules: Array<{
    name: string;
    version: string;
    title: string;
    featureFlag?: string;
  }>;
}

// --- Content Models ---
export interface WorkspaceItem {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  classification: string;
  department: string | null;
  created_at: string;
  updated_at: string;
}

export interface FolderItem {
  id: string;
  tenant_id: string;
  workspace_id: string;
  parent_id: string | null;
  name: string;
  path: string;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  tenant_id: string;
  workspace_id: string;
  folder_id: string | null;
  name: string;
  description: string | null;
  classification: string;
  department: string | null;
  mime_type: string | null;
  file_extension: string | null;
  size_bytes: number | null;
  content_hash: string | null;
  status: string;
  is_record: boolean;
  is_trashed: boolean;
  checkout_by_id: string | null;
  checkout_at: string | null;
  tags: string[];
  version_count: number;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersionItem {
  id: string;
  document_id: string;
  version_number: number;
  name: string;
  mime_type: string | null;
  size_bytes: number | null;
  content_hash: string | null;
  status: string;
  scan_result: string | null;
  ocr_status: string | null;
  comment: string | null;
  created_by_id: string | null;
  created_at: string;
}

export interface DocumentCommentItem {
  id: string;
  document_id: string;
  user_id: string;
  user_email: string;
  body: string;
  created_at: string;
}

export interface DocumentOcrText {
  document_id: string;
  status: "uploaded" | "scanning" | "processing" | "ready" | "blocked" | "failed" | string;
  extracted_text: string;
  page_count: number;
  confidence: number;
  language: string;
  processing_time_ms: number;
  ocr_engine: string;
  error_message: string | null;
  updated_at: string;
}

// --- Records Models ---
export interface RetentionScheduleItem {
  id: string;
  name: string;
  description: string | null;
  schedule_code: string | null;
  retention_years: number;
  department: string | null;
  classification: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LegalHoldItem {
  id: string;
  name: string;
  description: string | null;
  matter_number: string | null;
  status: string;
  placed_by_email: string;
  released_at: string | null;
  target_count: number;
  created_at: string;
}

export interface CreateLegalHoldPayload {
  name: string;
  description?: string;
  matter_number?: string;
  document_ids?: string[];
}

export interface CreateRetentionSchedulePayload {
  name: string;
  description?: string;
  schedule_code: string;
  retention_years: number;
  department?: string;
  classification?: string;
}

// --- Workflow Models ---
export interface WorkflowTaskItem {
  id: string;
  document_id: string;
  document_name: string | null;
  title: string;
  description: string | null;
  task_type: string;
  status: string;
  priority: string;
  submitted_by_email: string;
  assigned_to_email: string | null;
  decision_by_email: string | null;
  decision_at: string | null;
  decision_reason: string | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTaskPayload {
  document_id: string;
  title: string;
  description?: string;
  assigned_to_email?: string;
  priority?: string;
}

// --- Search Models ---
export interface SearchResultItem {
  id: string;
  name: string;
  description: string | null;
  classification: string;
  department: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  status: string;
  is_record: boolean;
  created_at: string;
  rank: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  page: number;
  page_size: number;
  results: SearchResultItem[];
  facets: {
    classifications: Record<string, number>;
    departments: Record<string, number>;
  };
}

// --- Admin Models ---
export interface AdminUserItem {
  id: string;
  tenant_id: string;
  email: string;
  username: string;
  first_name: string | null;
  last_name: string | null;
  roles: string[];
  department: string | null;
  clearance_level: number;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface AdminKPIs {
  total_users: number;
  active_users: number;
  total_documents: number;
  total_records: number;
  active_holds: number;
  held_documents: number;
  pending_tasks: number;
  audit_events_24h: number;
  storage_bytes_total: number;
  storage_mb_total: number;
}

export interface ServiceHealth {
  status: string;
  details?: Record<string, unknown>;
  error?: string;
}

export interface SystemHealthReport {
  overall_status: string;
  services: {
    postgres: ServiceHealth;
    redis: ServiceHealth;
    opa: ServiceHealth;
    minio: ServiceHealth;
    clamav: ServiceHealth;
  };
  product: {
    name: string;
    version: string;
    compliance: string[];
  };
}

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)elixir_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

export class ElixirApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = "") {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers = new Headers(options.headers || {});

    // Set JSON content type if body exists and is string and not already set
    if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    // Attach CSRF token on mutating requests
    const method = (options.method || "GET").toUpperCase();
    if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
      const csrf = getCsrfToken();
      if (csrf && !headers.has("X-CSRF-Token")) {
        headers.set("X-CSRF-Token", csrf);
      }
    }

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: "include", // Send session cookies
    });

    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("elixir:unauthorized"));
    } else if (response.status === 403) {
      window.dispatchEvent(new CustomEvent("elixir:forbidden"));
    }

    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }
      throw new ApiError(response.status, response.statusText, errorBody);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json() as Promise<T>;
  }

  // --- Identity & Session Endpoints ---
  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>("/api/v1/auth/me");
  }

  async loginWithPassword(credentials: DirectTokenPayload): Promise<UserProfile> {
    return this.request<UserProfile>("/api/v1/auth/token", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
  }

  async logout(): Promise<void> {
    await this.request<void>("/api/v1/auth/logout", {
      method: "POST",
    });
  }

  async stepUpMfa(payload: StepUpPayload): Promise<{ status: string }> {
    return this.request<{ status: string }>("/api/v1/auth/step-up", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // --- Audit Ledger Endpoints ---
  async listAuditEvents(page = 1, pageSize = 50): Promise<AuditListResponse> {
    return this.request<AuditListResponse>(
      `/api/v1/audit/events?page=${page}&page_size=${pageSize}`
    );
  }

  async verifyAuditChain(): Promise<AuditVerificationSummary> {
    return this.request<AuditVerificationSummary>("/api/v1/audit/verify", {
      method: "POST",
    });
  }

  // --- System & Info Endpoints ---
  async getSystemInfo(): Promise<{ data: SystemInfo }> {
    return this.request<{ data: SystemInfo }>("/api/v1/system/info");
  }

  // --- Content Services Endpoints ---
  async listWorkspaces(): Promise<WorkspaceItem[]> {
    return this.request<WorkspaceItem[]>("/api/v1/content/workspaces");
  }

  async createWorkspace(data: { name: string; description?: string; classification?: string; department?: string }): Promise<WorkspaceItem> {
    return this.request<WorkspaceItem>("/api/v1/content/workspaces", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async listFolders(workspaceId: string, parentId?: string): Promise<FolderItem[]> {
    const query = parentId ? `?workspace_id=${workspaceId}&parent_id=${parentId}` : `?workspace_id=${workspaceId}`;
    return this.request<FolderItem[]>(`/api/v1/content/folders${query}`);
  }

  async createFolder(workspaceId: string, name: string, parentId?: string): Promise<FolderItem> {
    return this.request<FolderItem>("/api/v1/content/folders", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, name, parent_id: parentId || null }),
    });
  }

  async listDocuments(workspaceId?: string, folderId?: string): Promise<DocumentItem[]> {
    const params = new URLSearchParams();
    if (workspaceId) params.set("workspace_id", workspaceId);
    if (folderId) params.set("folder_id", folderId);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await this.request<{ items: DocumentItem[] } | DocumentItem[]>(`/api/v1/content/documents${qs}`);
    return Array.isArray(res) ? res : (res?.items || []);
  }

  async getDocument(documentId: string): Promise<DocumentItem> {
    return this.request<DocumentItem>(`/api/v1/content/documents/${documentId}`);
  }

  async uploadDocument(formData: FormData): Promise<DocumentItem> {
    return this.request<DocumentItem>("/api/v1/content/documents/upload", {
      method: "POST",
      body: formData,
    });
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.request<void>(`/api/v1/content/documents/${documentId}`, {
      method: "DELETE",
    });
  }

  async checkoutDocument(documentId: string): Promise<{ status: string; checkout_by_id: string; checkout_at: string }> {
    return this.request<{ status: string; checkout_by_id: string; checkout_at: string }>(
      `/api/v1/content/documents/${documentId}/checkout`,
      { method: "POST" }
    );
  }

  async checkinDocument(documentId: string, comment?: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(
      `/api/v1/content/documents/${documentId}/checkin`,
      {
        method: "POST",
        body: JSON.stringify({ comment }),
      }
    );
  }

  async listDocumentVersions(documentId: string): Promise<DocumentVersionItem[]> {
    return this.request<DocumentVersionItem[]>(`/api/v1/content/documents/${documentId}/versions`);
  }

  async listComments(documentId: string): Promise<DocumentCommentItem[]> {
    return this.request<DocumentCommentItem[]>(`/api/v1/content/documents/${documentId}/comments`);
  }

  async addComment(documentId: string, body: string): Promise<DocumentCommentItem> {
    return this.request<DocumentCommentItem>(`/api/v1/content/documents/${documentId}/comments`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
  }

  getDocumentDownloadUrl(documentId: string, versionId: string): string {
    return `${this.baseUrl}/api/v1/content/documents/${documentId}/versions/${versionId}/download`;
  }

  async getDocumentOcrText(documentId: string): Promise<DocumentOcrText> {
    return this.request<DocumentOcrText>(`/api/v1/content/documents/${documentId}/text`);
  }

  async retryDocumentOcr(documentId: string): Promise<{ document_id: string; status: string; message: string }> {
    return this.request<{ document_id: string; status: string; message: string }>(
      `/api/v1/content/documents/${documentId}/retry-ocr`,
      { method: "POST" }
    );
  }

  // --- Records & Retention Endpoints ---
  async listRetentionSchedules(): Promise<RetentionScheduleItem[]> {
    return this.request<RetentionScheduleItem[]>("/api/v1/records/schedules");
  }

  async createRetentionSchedule(payload: CreateRetentionSchedulePayload): Promise<RetentionScheduleItem> {
    return this.request<RetentionScheduleItem>("/api/v1/records/schedules", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async listLegalHolds(): Promise<LegalHoldItem[]> {
    return this.request<LegalHoldItem[]>("/api/v1/records/holds");
  }

  async createLegalHold(payload: CreateLegalHoldPayload): Promise<LegalHoldItem> {
    return this.request<LegalHoldItem>("/api/v1/records/holds", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async releaseLegalHold(holdId: string, reason?: string): Promise<{ status: string; released_at: string }> {
    return this.request<{ status: string; released_at: string }>(`/api/v1/records/holds/${holdId}/release`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || "Investigation concluded" }),
    });
  }

  async declareRecord(documentId: string): Promise<{ status: string; is_record: boolean }> {
    return this.request<{ status: string; is_record: boolean }>(`/api/v1/records/declare/${documentId}`, {
      method: "POST",
    });
  }

  async getDispositionQueue(): Promise<Array<{ document_id: string; name: string; retention_years: number; eligible_at: string; status: string }>> {
    return this.request<Array<{ document_id: string; name: string; retention_years: number; eligible_at: string; status: string }>>(
      "/api/v1/records/disposition-queue"
    );
  }

  // --- Workflow Endpoints ---
  async listWorkflowTasks(status?: string, assignedToMe = false): Promise<WorkflowTaskItem[]> {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (assignedToMe) params.set("assigned_to_me", "true");
    const qs = params.toString() ? `?${params.toString()}` : "";
    return this.request<WorkflowTaskItem[]>(`/api/v1/workflow/tasks${qs}`);
  }

  async createWorkflowTask(payload: CreateTaskPayload): Promise<WorkflowTaskItem> {
    return this.request<WorkflowTaskItem>("/api/v1/workflow/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async decideWorkflowTask(taskId: string, decision: "approved" | "rejected", reason: string): Promise<WorkflowTaskItem> {
    return this.request<WorkflowTaskItem>(`/api/v1/workflow/tasks/${taskId}/complete`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    });
  }

  // --- Search Endpoints ---
  async search(query: string, options: { classification?: string; department?: string; status?: string; page?: number } = {}): Promise<SearchResponse> {
    const params = new URLSearchParams();
    params.set("q", query);
    if (options.classification) params.set("classification", options.classification);
    if (options.department) params.set("department", options.department);
    if (options.status) params.set("status", options.status);
    if (options.page) params.set("page", options.page.toString());
    return this.request<SearchResponse>(`/api/v1/search?${params.toString()}`);
  }

  // --- Admin Endpoints ---
  async listAdminUsers(page = 1, pageSize = 50): Promise<{ items: AdminUserItem[]; total: number; page: number; page_size: number }> {
    return this.request<{ items: AdminUserItem[]; total: number; page: number; page_size: number }>(
      `/api/v1/admin/users?page=${page}&page_size=${pageSize}`
    );
  }

  async updateAdminUser(userId: string, data: { roles?: string[]; is_active?: boolean; clearance_level?: number; department?: string }): Promise<AdminUserItem> {
    return this.request<AdminUserItem>(`/api/v1/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async getAdminKPIs(): Promise<AdminKPIs> {
    return this.request<AdminKPIs>("/api/v1/admin/kpis");
  }

  async getSystemHealth(): Promise<SystemHealthReport> {
    return this.request<SystemHealthReport>("/api/v1/admin/health");
  }
}

export const apiClient = new ElixirApiClient();
