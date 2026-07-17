import { describe, expect, it, vi } from "vitest";
import type { QueryClient } from "@tanstack/react-query";
import { apiErrorMessage, refreshAppState } from "./appState";

describe("refreshAppState", () => {
  it("invalidates every query so all views refetch", () => {
    const qc = { invalidateQueries: vi.fn().mockResolvedValue(undefined) };
    refreshAppState(qc as unknown as QueryClient);
    expect(qc.invalidateQueries).toHaveBeenCalledTimes(1);
    expect(qc.invalidateQueries).toHaveBeenCalledWith();
  });
});

describe("apiErrorMessage", () => {
  it("maps missing response to a network error", () => {
    expect(apiErrorMessage({ response: undefined, message: "Network Error" }, "fallback"))
      .toBe("Unable to reach the backend. Is it running?");
  });

  it("maps 401 to an authentication error", () => {
    expect(apiErrorMessage({ response: { status: 401, data: {} } }, "fallback"))
      .toBe("Authentication failed. Check your API key.");
  });

  it("prefers the backend detail message", () => {
    expect(
      apiErrorMessage(
        { response: { status: 400, data: { detail: "Anthropic rejected the API key: HTTP 401" } } },
        "fallback",
      ),
    ).toBe("Anthropic rejected the API key: HTTP 401");
  });

  it("prefixes authentication context on 401 details", () => {
    expect(
      apiErrorMessage({ response: { status: 401, data: { detail: "bad key" } } }, "fallback"),
    ).toBe("Authentication failed. bad key");
  });

  it("maps 502 to provider unreachable", () => {
    expect(apiErrorMessage({ response: { status: 502, data: {} } }, "fallback"))
      .toBe("Unable to reach provider.");
  });

  it("maps 404 to resource unavailable", () => {
    expect(apiErrorMessage({ response: { status: 404, data: {} } }, "fallback"))
      .toBe("Resource no longer available.");
  });

  it("falls back for unknown errors", () => {
    expect(apiErrorMessage(new Error("boom"), "Something failed")).toBe("Something failed");
  });
});
