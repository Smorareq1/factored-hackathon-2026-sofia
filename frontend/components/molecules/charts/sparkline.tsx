"use client";

import { type KeyboardEvent, type PointerEvent, useState } from "react";

import { useElementWidth } from "@/lib/hooks";

import { ChartTooltip } from "./chart-tooltip";

export interface SparkPoint {
  label: string;
  value: number;
}

interface Props {
  data: SparkPoint[];
  /** Resumen para lectores de pantalla (la idea, no los números uno por uno). */
  label: string;
  height?: number;
  format?: (value: number) => string;
}

const PAD = { top: 10, right: 8, bottom: 6, left: 8 };

/** Línea de 2 px con lavado al 10 %, punto final con anillo y cruz al pasar el cursor (o con las flechas). */
export function Sparkline({ data, label, height = 56, format = (v) => String(v) }: Props) {
  const [ref, width] = useElementWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const max = Math.max(1, ...data.map((d) => d.value)) * 1.15;
  const innerW = Math.max(0, width - PAD.left - PAD.right);
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const points = data.map((d, i) => [x(i), y(d.value)] as const);
  const line = points.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`).join("");
  const area = points.length > 1 ? `${line}L${points.at(-1)![0]},${PAD.top + innerH}L${points[0][0]},${PAD.top + innerH}Z` : "";
  const last = data.length - 1;
  const shown = active ?? last;

  function onMove(event: PointerEvent<SVGSVGElement>) {
    if (data.length === 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left - PAD.left) / Math.max(1, innerW);
    setActive(Math.max(0, Math.min(last, Math.round(ratio * last))));
  }

  function onKey(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const from = active ?? last;
    setActive(Math.max(0, Math.min(last, from + (event.key === "ArrowRight" ? 1 : -1))));
  }

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && data.length > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={label}
          tabIndex={0}
          onPointerMove={onMove}
          onPointerLeave={() => setActive(null)}
          onBlur={() => setActive(null)}
          onKeyDown={onKey}
          className="block overflow-visible rounded-md outline-offset-4"
        >
          <line x1={PAD.left} x2={width - PAD.right} y1={PAD.top + innerH} y2={PAD.top + innerH} stroke="var(--grid)" />
          {area && <path d={area} fill="var(--surface-3)" className="animate-fade" />}
          {points.length > 1 && (
            <path
              d={line}
              fill="none"
              stroke="var(--series-1)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              pathLength={1}
              className="stroke-draw"
            />
          )}
          {active !== null && (
            <line x1={x(active)} x2={x(active)} y1={PAD.top - 4} y2={PAD.top + innerH} stroke="var(--line-strong)" />
          )}
          <circle
            cx={x(shown)}
            cy={y(data[shown].value)}
            r={4}
            fill="var(--series-1)"
            stroke="var(--bg)"
            strokeWidth={2}
            className="transition-[cx,cy] duration-150"
          />
        </svg>
      )}
      {active !== null && data[active] && (
        <ChartTooltip x={x(active)} y={y(data[active].value)}>
          {data[active].label} · {format(data[active].value)}
        </ChartTooltip>
      )}
    </div>
  );
}
