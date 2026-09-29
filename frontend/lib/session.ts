// Sesión de la demo: token en sessionStorage (se borra al cerrar la pestaña), nunca en localStorage.
import type { DemoCustomer, Language, Role, SystemVersion } from "./types";

const KEY = "sofia.session";

export interface StoredSession {
  token: string;
  role: Role;
  expiresAt: string;
  label: string;
  country: DemoCustomer["country"] | null;
  language: Language;
  threadId: string;
  /** Sistema del hilo actual: el selector Sofía / Baseline abre un hilo nuevo al cambiar (§8.7). */
  system?: SystemVersion;
}

export function loadSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: StoredSession): void {
  window.sessionStorage.setItem(KEY, JSON.stringify(session));
}

export function updateSession(patch: Partial<StoredSession>): StoredSession | null {
  const current = loadSession();
  if (!current) return null;
  const next = { ...current, ...patch };
  saveSession(next);
  return next;
}

export function clearSession(): void {
  window.sessionStorage.removeItem(KEY);
}

export function newThreadId(): string {
  return `th-${crypto.randomUUID().replace(/-/g, "").slice(0, 20)}`;
}
