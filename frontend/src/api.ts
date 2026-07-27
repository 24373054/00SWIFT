import type { BootstrapPayload, CommandCenterPayload, ProductionPaymentsPayload } from "./types";

const simulationHeadersEnabled = () => {
  const host = typeof window === "undefined" ? "" : window.location.hostname;
  return import.meta.env.VITE_SIMULATION_MODE === "true" || host === "127.0.0.1" || host === "localhost";
};

type SandboxHeaderProfile = "none" | "ui" | "production";

const headersFor = (role: string, sandboxProfile: SandboxHeaderProfile = "none"): HeadersInit => ({
  Accept: "application/json",
  ...(sandboxProfile === "ui" && simulationHeadersEnabled()
    ? {
        "X-User-Role": role,
        "X-User-Subject": "institutional-ui-user",
      }
    : {}),
  ...(sandboxProfile === "production" && simulationHeadersEnabled()
    ? { "X-Participant-ID": "SANDBOX-ORIGIN" }
    : {}),
});

async function getJson<T>(path: string, role: string, sandboxProfile: SandboxHeaderProfile = "none"): Promise<T> {
  const response = await fetch(path, { headers: headersFor(role, sandboxProfile) });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as T;
}

export async function loadBootstrap(role: string): Promise<BootstrapPayload> {
  return getJson<BootstrapPayload>("/nextgen/v1/ui/bootstrap", role, "ui");
}

export async function loadCommandCenter(role: string): Promise<CommandCenterPayload> {
  return getJson<CommandCenterPayload>("/nextgen/v1/ui/command-center", role, "ui");
}

export async function loadProductionPayments(role: string): Promise<ProductionPaymentsPayload> {
  return getJson<ProductionPaymentsPayload>("/production/v1/payments", role, "production");
}

export async function submitProductionPayment(role: string, payload: Record<string, unknown>, idempotencyKey: string): Promise<unknown> {
  const body = JSON.stringify(payload);
  const digestBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body));
  const digest = btoa(String.fromCharCode(...Array.from(new Uint8Array(digestBytes))));
  const response = await fetch("/production/v1/payments", {
    method: "POST",
    headers: { ...headersFor(role, "production"), "Content-Type": "application/json", "Idempotency-Key": idempotencyKey, "Content-Digest": `sha-256=:${digest}:` },
    body,
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}
