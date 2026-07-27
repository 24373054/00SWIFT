import type { BootstrapPayload, CommandCenterPayload, ProductionPaymentsPayload } from "./types";

const simulationHeadersEnabled = import.meta.env.VITE_SIMULATION_MODE === "true";

const headersFor = (role: string, simulation = false): HeadersInit => ({
  Accept: "application/json",
  ...(simulation && simulationHeadersEnabled
    ? {
        "X-User-Role": role,
        "X-User-Subject": "institutional-ui-user",
        "X-Participant-ID": "SANDBOX-ORIGIN",
      }
    : {}),
});

async function getJson<T>(path: string, role: string, simulation = false): Promise<T> {
  const response = await fetch(path, { headers: headersFor(role, simulation) });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as T;
}

export async function loadBootstrap(role: string): Promise<BootstrapPayload> {
  return getJson<BootstrapPayload>("/nextgen/v1/ui/bootstrap", role, true);
}

export async function loadCommandCenter(role: string): Promise<CommandCenterPayload> {
  return getJson<CommandCenterPayload>("/nextgen/v1/ui/command-center", role, true);
}

export async function loadProductionPayments(role: string): Promise<ProductionPaymentsPayload> {
  return getJson<ProductionPaymentsPayload>("/production/v1/payments", role);
}

export async function submitProductionPayment(role: string, payload: Record<string, unknown>, idempotencyKey: string): Promise<unknown> {
  const body = JSON.stringify(payload);
  const digestBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body));
  const digest = btoa(String.fromCharCode(...Array.from(new Uint8Array(digestBytes))));
  const response = await fetch("/production/v1/payments", {
    method: "POST",
    headers: { ...headersFor(role), "Content-Type": "application/json", "Idempotency-Key": idempotencyKey, "Content-Digest": `sha-256=:${digest}:` },
    body,
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}
