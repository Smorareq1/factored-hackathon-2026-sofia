// Tonos semánticos del sistema. Las clases van completas (Tailwind no ve clases armadas por interpolación).
export type Tone = "neutral" | "brand" | "accent" | "ok" | "warn" | "danger" | "info";

export const TONE_SOFT: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2",
  brand: "bg-brand-soft text-brand-ink",
  accent: "bg-accent-soft text-accent-ink",
  ok: "bg-ok-soft text-ok-ink",
  warn: "bg-warn-soft text-warn-ink",
  danger: "bg-danger-soft text-danger-ink",
  info: "bg-info-soft text-info-ink",
};

// El texto sobre cada relleno sale de un token `on-*`: blanco en el tema claro, tinta en el tema noche.
export const TONE_SOLID: Record<Tone, string> = {
  neutral: "bg-ink text-on-ink",
  brand: "bg-brand text-on-brand",
  accent: "bg-accent text-on-accent",
  ok: "bg-ok text-on-ok",
  warn: "bg-warn text-on-warn",
  danger: "bg-danger text-on-danger",
  info: "bg-info text-on-info",
};

export const TONE_OUTLINE: Record<Tone, string> = {
  neutral: "ring-[1.5px] ring-inset ring-ink-3 text-ink-2",
  brand: "ring-[1.5px] ring-inset ring-brand text-brand-ink",
  accent: "ring-[1.5px] ring-inset ring-accent-strong text-accent-ink",
  ok: "ring-[1.5px] ring-inset ring-ok text-ok-ink",
  warn: "ring-[1.5px] ring-inset ring-warn text-warn-ink",
  danger: "ring-[1.5px] ring-inset ring-danger text-danger-ink",
  info: "ring-[1.5px] ring-inset ring-info text-info-ink",
};

export const TONE_FILL: Record<Tone, string> = {
  neutral: "bg-ink-4",
  brand: "bg-brand",
  accent: "bg-accent",
  ok: "bg-ok",
  warn: "bg-warn",
  danger: "bg-danger",
  info: "bg-info",
};

export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-ink-3",
  brand: "text-brand-ink",
  accent: "text-accent-ink",
  ok: "text-ok-ink",
  warn: "text-warn-ink",
  danger: "text-danger-ink",
  info: "text-info-ink",
};
