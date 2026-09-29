// Espejo de contracts/ (§9.4 handoff, §9.7 eventos de capa, sesión §9.2).
// TODO(D2): generarlos desde el JSON Schema exportado de contracts/ en vez de mantenerlos a mano.

export type Language = "es" | "pt";
export type Route = "auto" | "clarify" | "abstain" | "escalate" | "deny" | "reauth";
export type Layer = "PURPOSE" | "SENSE" | "INTERPRET" | "DECIDE" | "ORCHESTRATE" | "GOVERN" | "LEARN";
export type EventStatus = "ok" | "warn" | "error" | "skipped";
export type GoalStatus = "open" | "resolved" | "escalated" | "abstained" | "denied";
export type Role = "customer" | "agent";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface LayerEvent {
  turn: number;
  layer: Layer;
  node: string;
  status: EventStatus;
  code: string;
  params: Record<string, JsonValue>;
  started_at: string;
  duration_ms: number;
  span_id: string | null;
}

export interface TransactionCard {
  transaction_id: string;
  date: string;
  merchant: string;
  amount: string;
  currency: string;
  amount_display: string;
}

export interface CandidateCard extends TransactionCard {
  option: number;
}

export interface CaseCard {
  dispute_id: string;
  status: string;
  status_display: string;
  verified: boolean;
}

export interface AgentMessage {
  text: string;
  language: Language;
  route: Route | null;
  quick_replies: string[];
  candidates: CandidateCard[];
  subject: TransactionCard | null;
  case: CaseCard | null;
}

export interface TurnDone {
  turn: number;
  route: Route | null;
  goal_status: GoalStatus | null;
  latency_ms: number;
  trace_id: string | null;
}

export interface TurnError {
  code: string;
  message: string;
}

export interface HandoffFact {
  fact: string;
  source: string;
}

export interface HandoffAction {
  action: string;
  result: string;
  verified: boolean;
}

export interface Handoff {
  handoff_id: string;
  created_at: string;
  schema_version: string;
  language: Language;
  customer_id: string;
  authenticated: boolean;
  request_summary: string;
  customer_claim: string | null;
  verified_facts: HandoffFact[];
  actions_taken: HandoffAction[];
  open_questions: string[];
  risk_flags: string[];
  reason_for_handoff: string;
  system_version: SystemVersion;
  trace_id: string | null;
}

export type SystemVersion = "proposed" | "baseline";

/** LEARN: juicio del agente humano sobre la ficha (score `handoff_quality` en la traza). */
export interface HandoffFeedback {
  useful: boolean;
  missing_fields: string[];
  comment: string | null;
}

export interface HandoffFeedbackRecord extends HandoffFeedback {
  handoff_id: string;
  reviewer_id: string;
  submitted_at: string;
}

export interface DemoCustomer {
  document_number: string;
  label: string;
  country: "MX" | "CO" | "AR";
  role: Role;
}

export interface SessionChallenge {
  challenge_id: string;
  expires_at: string;
  simulated_otp: string | null;
}

export interface SessionToken {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  role: Role;
}

export interface SessionInfo {
  customer_id: string;
  role: Role;
  country: "MX" | "CO" | "AR" | null;
  expires_at: string;
}

export interface AgentMeta {
  purpose_version: string;
  prompt_version: string;
  model: string;
  bank: "fake" | "sim";
  auto_actions: boolean;
  langfuse_url: string | null;
  router_threshold: number;
  max_clarifications: number;
  baseline_available: boolean;
  tracing: boolean;
}

export interface ThreadSnapshot {
  thread_id: string;
  turn: number;
  language: Language | null;
  messages: { role: "customer" | "agent"; text: string; turn: number }[];
  goal: { type: string; status: GoalStatus; opened_turn: number } | null;
  pending_confirmation: boolean;
  last_response: AgentMessage | null;
}
