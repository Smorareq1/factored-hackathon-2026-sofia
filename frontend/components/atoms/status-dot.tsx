import { cn } from "@/lib/cn";

import { TONE_FILL, type Tone } from "./tone";

/** Punto de estado; `pulse` agrega una onda que se expande (algo está vivo o en curso). */
export function StatusDot({ tone = "ok", pulse = false, size = 8, className }: { tone?: Tone; pulse?: boolean; size?: number; className?: string }) {
  return (
    <span className={cn("relative inline-flex shrink-0", className)} style={{ width: size, height: size }} aria-hidden>
      {pulse && <span className={cn("absolute inset-0 animate-ping-soft rounded-full", TONE_FILL[tone])} />}
      <span className={cn("relative size-full rounded-full", TONE_FILL[tone])} />
    </span>
  );
}
