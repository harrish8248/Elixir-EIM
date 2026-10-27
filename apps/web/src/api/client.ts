/**
 * Generated Typed API Client for Elixir Enterprise Information Management.
 * Generated from OpenAPI 3.1.0 specification at /api/v1/openapi.json.
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

    // Set JSON content type if body exists and not already set
    if (options.body && !headers.has("Content-Type")) {
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
}

export const apiClient = new ElixirApiClient();
