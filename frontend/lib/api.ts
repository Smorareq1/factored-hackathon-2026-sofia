// Cliente del agente (BFF): sesión, chat por SSE, hilo y consola. El navegador no habla con SIM directo.
import type {
  AgentMeta,
  DemoCustomer,
  Handoff,
  HandoffFeedback,
  HandoffFeedbackRecord,
  SessionChallenge,
  SessionInfo,
  SessionToken,
  ThreadSnapshot,
} from "./types";

export const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8001";
export const LANGFUSE_URL = process.env.NEXT_PUBLIC_LANGFUSE_URL ?? null;
/** Local (`make langfuse`): `sofia-local`. En cloud, el id real del proyecto de Langfuse. */
export const LANGFUSE_PROJECT_ID = process.env.NEXT_PUBLIC_LANGFUSE_PROJECT_ID || "sofia-local";
export const LANGFUSE_TRACE_BASE = LANGFUSE_URL
  ? `${LANGFUSE_URL.replace(/\/$/, "")}/project/${LANGFUSE_PROJECT_ID}/traces`
  : null;

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`${status} ${detail}`);
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${AGENT_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof body.detail === "string" ? body.detail : response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  meta: () => request<AgentMeta>("/v1/meta"),
  demoCustomers: () => request<DemoCustomer[]>("/v1/demo/customers"),
  startSession: (document_number: string) =>
    request<SessionChallenge>("/v1/session", { method: "POST", body: JSON.stringify({ document_number }) }),
  verifySession: (challenge_id: string, otp: string) =>
    request<SessionToken>("/v1/session/verify", { method: "POST", body: JSON.stringify({ challenge_id, otp }) }),
  me: (token: string) => request<SessionInfo>("/v1/session/me", {}, token),
  thread: (token: string, threadId: string) => request<ThreadSnapshot>(`/v1/threads/${threadId}`, {}, token),
  handoffs: (token: string) => request<{ items: Handoff[] }>("/v1/console/handoffs", {}, token),
  handoff: (token: string, id: string) => request<Handoff>(`/v1/console/handoffs/${id}`, {}, token),
  /** `null` si la ficha todavía no tiene feedback (404). */
  feedback: (token: string, id: string) =>
    request<HandoffFeedbackRecord>(`/v1/console/handoffs/${id}/feedback`, {}, token).catch((error: unknown) => {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }),
  sendFeedback: (token: string, id: string, feedback: HandoffFeedback) =>
    request<HandoffFeedbackRecord>(`/v1/console/handoffs/${id}/feedback`, { method: "POST", body: JSON.stringify(feedback) }, token),
};
