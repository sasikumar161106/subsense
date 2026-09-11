export const API_BASE = "/api/v1";

export interface RequestOptions extends RequestInit {
  tenantId?: string;
  userRole?: string;
  userId?: string;
}

export async function fetchApi<T = any>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  // Inject session context
  const token = localStorage.getItem("subsense_token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.tenantId) {
    headers.set("x-tenant-id", options.tenantId);
  }
  if (options.userRole) {
    headers.set("x-user-role", options.userRole);
  }
  if (options.userId) {
    headers.set("x-user-id", options.userId);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status} ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorMsg = errJson.error || errJson.message || errorMsg;
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  if (response.status === 204) {
    return null as T;
  }

  const text = await response.text();
  if (!text || text.trim() === "") {
    return null as T;
  }

  return JSON.parse(text);
}
