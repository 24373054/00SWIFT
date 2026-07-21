import { fallbackBootstrap, fallbackCommandCenter } from "./fixtures";
import type { BootstrapPayload, CommandCenterPayload } from "./types";

const headersFor = (role: string): HeadersInit => ({
  Accept: "application/json",
  "X-User-Role": role,
  "X-User-Subject": "institutional-ui-user",
});

async function getJson<T>(path: string, role: string): Promise<T> {
  const response = await fetch(path, { headers: headersFor(role) });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as T;
}

export async function loadBootstrap(role: string): Promise<BootstrapPayload> {
  try {
    return await getJson<BootstrapPayload>("/nextgen/v1/ui/bootstrap", role);
  } catch {
    return {
      ...fallbackBootstrap,
      identity: { ...fallbackBootstrap.identity, role },
    };
  }
}

export async function loadCommandCenter(role: string): Promise<CommandCenterPayload> {
  try {
    return await getJson<CommandCenterPayload>("/nextgen/v1/ui/command-center", role);
  } catch {
    return fallbackCommandCenter;
  }
}
