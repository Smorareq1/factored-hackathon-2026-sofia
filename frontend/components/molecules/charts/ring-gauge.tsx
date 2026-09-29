import type { ReactNode } from "react";

import type { Tone } from "@/components/atoms/tone";

const STROKE: Record<Tone, string> = {
  neutral: "var(--ink-4)",
  brand: "var(--series-1)",
  accent: "var(--series-2)",
  ok: "var(--ok)",
  warn: "var(--warn)",
  danger: "var(--danger)",
  info: "var(--info)",
};

/** Anillo de progreso que se dibuja desde las 12 en punto; el centro lleva el valor en texto. */
export function RingGauge({
  value,
  max,
  label,
  size = 76,
  stroke = 7,
  tone = "brand",
  children,
}: {
  value: number;
  max: number;
  label: string;
  size?: number;
  stroke?: number;
  tone?: Tone;
  children?: ReactNode;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const r = (size - stroke) / 2;
  return (
    <div className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} role="img" aria-label={label} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        {pct > 0 && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={STROKE[tone]}
            strokeWidth={stroke}
            strokeLinecap="round"
            pathLength={100}
            strokeDasharray={`${pct} 100`}
            style={{ strokeDashoffset: pct, animation: "draw 900ms var(--ease-out-soft) 120ms forwards" }}
          />
        )}
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}
