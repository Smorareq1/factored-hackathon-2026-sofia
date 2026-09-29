import { cn } from "@/lib/cn";

import { Icon, type IconName } from "./icon";
import { SofiaMark } from "./logo";
import { TONE_SOLID, type Tone } from "./tone";

/** Avatar de Sofía. `thinking` agrega un arco sólido que gira mientras las capas trabajan. */
export function SofiaAvatar({ size = 32, thinking = false, className }: { size?: number; thinking?: boolean; className?: string }) {
  return (
    <span className={cn("relative inline-grid shrink-0 place-items-center", className)} style={{ width: size, height: size }}>
      {thinking && (
        <span aria-hidden className="absolute -inset-[4px] animate-orbit rounded-full border-2 border-surface-3 border-t-brand border-r-brand" />
      )}
      <span className="overflow-hidden rounded-full">
        <SofiaMark size={size} />
      </span>
    </span>
  );
}

/**
 * Avatar genérico: icono o iniciales sobre un tono sólido.
 * Identidades: cliente = `neutral` (tinta), Sofía = marca, persona del banco = `accent` (sol).
 */
export function Avatar({
  icon,
  label,
  tone = "neutral",
  size = 32,
  className,
}: {
  icon?: IconName;
  label?: string;
  tone?: Tone;
  size?: number;
  className?: string;
}) {
  const initials = label
    ?.split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  return (
    <span
      className={cn("inline-grid shrink-0 place-items-center rounded-full font-bold", TONE_SOLID[tone], className)}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      aria-hidden
    >
      {icon ? <Icon name={icon} size={Math.round(size * 0.52)} strokeWidth={2} /> : initials}
    </span>
  );
}

// Paleta de figuras: mismo comercio, mismo color en toda la app.
const MONOGRAM = ["bg-fig-cobalt text-white", "bg-fig-ink text-fig-paper", "bg-fig-sun text-on-accent", "bg-fig-coral text-on-accent", "bg-surface-3 text-ink"] as const;

/** Monograma de comercio: cuadrado sólido con la inicial. */
export function MerchantMonogram({ name, size = 36 }: { name: string; size?: number }) {
  const hash = [...name].reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) >>> 0, 7);
  return (
    <span
      aria-hidden
      className={cn("inline-grid shrink-0 place-items-center rounded-xl font-bold", MONOGRAM[hash % MONOGRAM.length])}
      style={{ width: size, height: size, fontSize: size * 0.44 }}
    >
      {name.trim().charAt(0).toUpperCase()}
    </span>
  );
}
