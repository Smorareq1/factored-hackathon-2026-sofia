// Presentación de los handoffs en la consola: icono y tono por motivo, antigüedad y completitud de la ficha.
import type { IconName } from "@/components/atoms/icon";
import type { Tone } from "@/components/atoms/tone";

import type { Handoff } from "./types";

export function reasonIcon(reason: string): IconName {
  if (reason.startsWith("POL-")) return "layer-decide";
  if (reason === "customer_request") return "headset";
  if (reason === "tool_unavailable") return "plug";
  if (reason === "kill_switch") return "ban";
  return "alert-circle";
}

export function reasonTone(reason: string): Tone {
  if (reason.startsWith("POL-")) return "accent";
  if (reason === "customer_request") return "info";
  if (reason === "tool_unavailable") return "warn";
  return "danger";
}

export function ageMinutes(iso: string, now: number): number {
  return Math.max(0, (now - Date.parse(iso)) / 60_000);
}

/** "hace 3 min" / "recién llegado" para encabezados (`fresh` cambia el texto del primer minuto). */
export function sinceLabel(minutes: number, fresh = "recién llegado"): string {
  return minutes < 1 ? fresh : `hace ${formatAge(minutes)}`;
}

export function formatAge(minutes: number): string {
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `${Math.floor(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours} h ${Math.floor(minutes % 60)} min` : `${Math.floor(hours / 24)} d`;
}

/** Campos §9.4 que el agente humano necesita para atender sin volver a preguntar (vista de la consola). */
export function completeness(handoff: Handoff): { label: string; ok: boolean }[] {
  return [
    { label: "Resumen", ok: handoff.request_summary.trim().length > 0 },
    { label: "Cliente autenticado", ok: handoff.authenticated },
    { label: "Reclamo del cliente", ok: handoff.customer_claim !== null },
    { label: "Hechos con fuente", ok: handoff.verified_facts.length > 0 && handoff.verified_facts.every((f) => f.source) },
    { label: "Acciones registradas", ok: handoff.actions_taken.length > 0 },
    { label: "Motivo de transferencia", ok: Boolean(handoff.reason_for_handoff) },
  ];
}
