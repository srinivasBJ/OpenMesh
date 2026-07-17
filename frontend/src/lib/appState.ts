import type { QueryClient } from "@tanstack/react-query";

/**
 * Centralized state refresh: after any action that changes backend state
 * (session start/stop/terminate, provider connect/select/disconnect,
 * workspace/project creation, demo lifecycle), every live view — provider
 * status, active model, agents, traces, graph, event bus, workspaces —
 * refetches. No browser refresh, ever.
 */
export function refreshAppState(qc: QueryClient): void {
  void qc.invalidateQueries();
}

/**
 * Human-readable error for API failures. Never silently fail:
 * - no response  → network problem
 * - 401/403      → authentication problem
 * - body detail  → backend's own message
 */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const err = error as {
    response?: { status?: number; data?: { detail?: unknown } };
    message?: string;
  };
  if (err && typeof err === "object" && "response" in err) {
    const response = err.response;
    if (!response) return "Unable to reach the backend. Is it running?";
    const detail = response.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      if (response.status === 401 || response.status === 403) {
        return `Authentication failed. ${detail}`;
      }
      return detail;
    }
    if (response.status === 401 || response.status === 403) {
      return "Authentication failed. Check your API key.";
    }
    if (response.status === 502) return "Unable to reach provider.";
    if (response.status === 404) return "Resource no longer available.";
  }
  return fallback;
}
