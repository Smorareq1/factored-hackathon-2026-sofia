"use client";

import { Eyebrow } from "@/components/atoms/primitives";
import { Shape } from "@/components/atoms/shape";
import { cn } from "@/lib/cn";
import { t } from "@/lib/i18n";
import { LAYER_SHAPE, NODE_LAYER } from "@/lib/layers";
import type { Language, Layer, LayerEvent } from "@/lib/types";

interface Span {
  node: string;
  layer: Layer;
  start: number;
  end: number;
  toolMs: number;
  tools: LayerEvent[];
  failed: boolean;
}

/**
 * Cada evento trae `started_at` (cuándo se emitió) y `duration_ms` (desde que arrancó su nodo), así que el
 * inicio del nodo es `started_at - duration_ms` y su fin, el último evento. Las tool calls se registran al
 * cerrar el nodo con su propia duración: se dibujan como la porción final de la barra.
 */
function spansOf(events: LayerEvent[]): { spans: Span[]; total: number } {
  if (events.length === 0) return { spans: [], total: 0 };
  const starts = events.map((e) => Date.parse(e.started_at) - e.duration_ms);
  const t0 = Math.min(...starts);
  const byNode = new Map<string, Span>();
  events.forEach((event, i) => {
    const start = starts[i] - t0;
    const at = Date.parse(event.started_at) - t0;
    const span = byNode.get(event.node) ?? {
      node: event.node,
      layer: NODE_LAYER[event.node] ?? event.layer,
      start,
      end: at,
      toolMs: 0,
      tools: [],
      failed: false,
    };
    span.start = Math.min(span.start, start);
    span.end = Math.max(span.end, at);
    if (event.code === "tool_call") {
      span.toolMs += Number(event.params.ms) || 0;
      span.tools.push(event);
    }
    span.failed ||= event.status === "error";
    byNode.set(event.node, span);
  });
  const spans = [...byNode.values()].sort((a, b) => a.start - b.start);
  return { spans, total: Math.max(1, ...spans.map((s) => s.end)) };
}

const pct = (value: number, total: number) => `${(value / total) * 100}%`;

/** Cascada del turno: cuándo corrió cada nodo (bloque cobalto), cuánto tardó y cuánto fue esperar a las tools (tinta). */
export function TurnWaterfall({ events, lang }: { events: LayerEvent[]; lang: Language }) {
  const { spans, total } = spansOf(events);
  if (spans.length === 0) return null;
  return (
    <figure aria-label={t(lang, "waterfall")} className="space-y-2">
      <figcaption className="flex items-center justify-between">
        <Eyebrow>{t(lang, "waterfall")}</Eyebrow>
        <span className="flex items-center gap-3 text-[10px] text-ink-3">
          <span className="flex items-center gap-1">
            <span className="size-2 bg-brand" aria-hidden />
            {t(lang, "nodeTime")}
          </span>
          <span className="flex items-center gap-1">
            <span className="size-2 bg-ink" aria-hidden />
            {t(lang, "toolTime")}
          </span>
        </span>
      </figcaption>
      <div className="space-y-0.5">
        {spans.map((span, i) => {
          const duration = Math.max(0, span.end - span.start);
          return (
            <div
              key={span.node}
              tabIndex={0}
              className="group relative grid grid-cols-[92px_1fr_52px] items-center gap-2 py-1 text-[11px] outline-offset-1 hover:bg-surface-2"
            >
              <span className="flex min-w-0 items-center gap-1.5 font-mono font-semibold text-ink-2">
                <Shape kind={LAYER_SHAPE[span.layer]} color="current" size={9} className={span.failed ? "text-danger" : "text-ink-3"} />
                <span className="truncate">{span.node}</span>
              </span>
              <span className="relative h-3.5 bg-surface-2">
                <span
                  className={cn("absolute inset-y-0 flex origin-left animate-grow-x overflow-hidden", span.failed ? "bg-danger" : "bg-brand")}
                  style={{ left: pct(span.start, total), width: `max(3px, ${pct(duration, total)})`, animationDelay: `${i * 90}ms` }}
                >
                  {span.toolMs > 0 && (
                    <span
                      className="ml-auto h-full border-l-2 border-bg bg-ink"
                      style={{ width: `${Math.min(100, (span.toolMs / Math.max(1, duration)) * 100)}%` }}
                    />
                  )}
                </span>
              </span>
              <span className="text-right font-mono font-semibold text-ink-2 tabular-nums">{duration} ms</span>
              {span.tools.length > 0 && (
                <span className="pointer-events-none absolute top-full left-24 z-10 mt-1 hidden min-w-56 bg-ink p-2 font-mono text-[10px] leading-relaxed text-on-ink group-hover:block group-focus:block">
                  {span.tools.map((tool, j) => (
                    <span key={j} className="block whitespace-nowrap">
                      {String(tool.params.method)} {String(tool.params.path)} → {String(tool.params.http_status ?? "—")} · {String(tool.params.ms)} ms
                    </span>
                  ))}
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div className="mr-[60px] ml-[100px] flex justify-between border-t border-line pt-1 font-mono text-[10px] text-ink-3 tabular-nums" aria-hidden>
        <span>0</span>
        <span>{Math.round(total / 2)}</span>
        <span>{Math.round(total)} ms</span>
      </div>
    </figure>
  );
}
