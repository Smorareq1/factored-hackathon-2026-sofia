"use client";

import { useState } from "react";

import { useElementWidth } from "@/lib/hooks";

import { ChartTooltip } from "./chart-tooltip";

export interface Column {
  label: string;
  value: number;
}

interface Props {
  data: Column[];
  label: string;
  height?: number;
  format?: (value: number) => string;
}

const PAD = { top: 16, bottom: 4 };

/** Columnas de ≤ 24 px con tapa redondeada de 4 px y base cuadrada; etiqueta solo en el máximo. */
export function ColumnChart({ data, label, height = 72, format = (v) => String(v) }: Props) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const max = Math.max(1, ...data.map((d) => d.value));
  const band = data.length ? width / data.length : 0;
  const barW = Math.min(24, Math.max(3, band * 0.62));
  const innerH = height - PAD.top - PAD.bottom;
  const peak = data.reduce((best, d, i) => (d.value > (data[best]?.value ?? -1) ? i : best), 0);

  const columnPath = (cx: number, value: number) => {
    const h = Math.max(2, (value / max) * innerH);
    const x0 = cx - barW / 2;
    const top = PAD.top + innerH - h;
    const r = Math.min(4, barW / 2, h);
    return `M${x0},${PAD.top + innerH}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x0 + barW - r}Q${x0 + barW},${top} ${x0 + barW},${top + r}V${PAD.top + innerH}Z`;
  };

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={label} className="block overflow-visible">
          {data.map((d, i) => {
            const cx = band * i + band / 2;
            return (
              <g key={d.label} onPointerEnter={() => setActive(i)} onPointerLeave={() => setActive(null)}>
                <rect x={band * i} y={0} width={band} height={height} fill="transparent" />
                <path
                  d={columnPath(cx, d.value)}
                  fill={d.value > 0 ? "var(--series-1)" : "var(--grid)"}
                  opacity={active === null || active === i ? 1 : 0.45}
                  className="origin-bottom animate-grow-y transition-opacity duration-150 [transform-box:fill-box]"
                  style={{ animationDelay: `${i * 35}ms` }}
                />
                {i === peak && d.value > 0 && active === null && (
                  <text x={cx} y={PAD.top + innerH - (d.value / max) * innerH - 5} textAnchor="middle" className="fill-ink-2 text-[10px] font-semibold">
                    {format(d.value)}
                  </text>
                )}
              </g>
            );
          })}
          <line x1={0} x2={width} y1={PAD.top + innerH} y2={PAD.top + innerH} stroke="var(--line-strong)" />
        </svg>
      )}
      {active !== null && data[active] && (
        <ChartTooltip x={band * active + band / 2} y={PAD.top + innerH - (data[active].value / max) * innerH}>
          {data[active].label} · {format(data[active].value)}
        </ChartTooltip>
      )}
    </div>
  );
}
