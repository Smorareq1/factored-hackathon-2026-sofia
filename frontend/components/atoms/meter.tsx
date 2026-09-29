import { cn } from "@/lib/cn";

import { TONE_FILL, type Tone } from "./tone";

export interface MeterProps {
  /** 0..1 */
  value: number;
  /** Umbral (0..1) dibujado como una marca vertical: por ejemplo, la confianza mínima del router. */
  threshold?: number;
  tone?: Tone;
  label: string;
  className?: string;
}

/** Barra de medida con umbral. Crece desde la izquierda al montarse. */
export function Meter({ value, threshold, tone = "brand", label, className }: MeterProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <span
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      className={cn("relative inline-block h-1.5 w-full overflow-visible rounded-full bg-surface-3", className)}
    >
      <span
        className={cn("absolute inset-y-0 left-0 origin-left animate-grow-x rounded-full", TONE_FILL[tone])}
        style={{ width: `${pct}%` }}
      />
      {threshold !== undefined && (
        <span
          aria-hidden
          className="absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full bg-ink-2"
          style={{ left: `${threshold * 100}%` }}
        />
      )}
    </span>
  );
}
