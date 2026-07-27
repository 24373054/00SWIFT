import { afterEach, describe, expect, it, vi } from "vitest";

import { loadProductionPayments } from "./api";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("production payment API", () => {
  it("uses the sandbox participant identity only when simulation mode is enabled", async () => {
    vi.stubEnv("VITE_SIMULATION_MODE", "true");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadProductionPayments("payments_operator")).resolves.toEqual({ items: [] });

    expect(fetchMock).toHaveBeenCalledWith(
      "/production/v1/payments",
      expect.objectContaining({
        headers: expect.objectContaining({
          "X-Participant-ID": "SANDBOX-ORIGIN",
        }),
      }),
    );
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers).not.toHaveProperty("X-User-Role");
    expect(headers).not.toHaveProperty("X-User-Subject");
  });
});
