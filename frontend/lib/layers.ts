// Metadatos de las 7 capas para la UI: orden, icono y qué nodo del grafo pertenece a cuál.
import type { IconName } from "@/components/atoms/icon";

import type { EventStatus, Layer, LayerEvent, Route } from "./types";
import type { Tone } from "@/components/atoms/tone";

export const LAYERS: Layer[] = ["PURPOSE", "SENSE", "INTERPRET", "DECIDE", "ORCHESTRATE", "GOVERN", "LEARN"];

export const LAYER_ICON: Record<Layer, IconName> = {
  PURPOSE: "layer-purpose",
  SENSE: "layer-sense",
  INTERPRET: "layer-interpret",
  DECIDE: "layer-decide",
  ORCHESTRATE: "layer-orchestrate",
  GOVERN: "shield-check",
  LEARN: "layer-learn",
};

/** Nodo del grafo (agent/graph.py) → capa dueña, para la cascada de tiempos. */
export const NODE_LAYER: Record<string, Layer> = {
  sense: "SENSE",
  reauth: "SENSE",
  interpret: "INTERPRET",
  clarify: "INTERPRET",
  decide: "DECIDE",
  abstain: "DECIDE",
  act: "ORCHESTRATE",
  verify: "ORCHESTRATE",
  escalate: "ORCHESTRATE",
  respond: "ORCHESTRATE",
};

/** Orden en que SIM evalúa la política (primera regla que aplica, gana). */
export const POLICY_ORDER = ["POL-1", "POL-4", "POL-2", "POL-3", "POL-6", "POL-5"] as const;

export type Status = EventStatus | "idle";

export function worstStatus(events: LayerEvent[]): Status {
  if (events.length === 0) return "idle";
  if (events.some((e) => e.status === "error")) return "error";
  if (events.some((e) => e.status === "warn")) return "warn";
  return "ok";
}

export const STATUS_TONE: Record<Status, Tone> = { ok: "ok", warn: "warn", error: "danger", skipped: "neutral", idle: "neutral" };

/** Colores de ruta del plan: verde auto, ámbar aclarar/abstenerse, azul humano, rojo denegar o guarda. */
export const ROUTE_TONE: Record<Route, Tone> = {
  auto: "ok",
  clarify: "warn",
  abstain: "warn",
  escalate: "info",
  deny: "danger",
  reauth: "danger",
};

export const ROUTE_ICON: Record<Route, IconName> = {
  auto: "check-circle",
  clarify: "question",
  abstain: "minus-circle",
  escalate: "headset",
  deny: "ban",
  reauth: "lock",
};
