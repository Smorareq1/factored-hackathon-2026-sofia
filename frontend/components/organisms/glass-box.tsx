"use client";

// Caja de cristal (REQ-19): por turno, qué hizo cada una de las 7 capas. Se arma SOLO con eventos de capa
// (`code` + `params`); cada capa se expande a su JSON crudo para la defensa en vivo.
// Lenguaje visual: un panel de instrumentos. Cada capa es una figura sólida (LAYER_SHAPE) sobre el color de su
// estado; los números van grandes y las tool calls se leen como un recibo.
import { useState } from "react";

import { IconButton } from "@/components/atoms/button";
import { Icon } from "@/components/atoms/icon";
import { BlockMeter } from "@/components/atoms/meter";
import { Shape } from "@/components/atoms/shape";
import { TONE_FILL, TONE_SOLID, TONE_TEXT } from "@/components/atoms/tone";
import { ColumnChart } from "@/components/molecules/charts/column-chart";
import { JsonView, PolicyLadder } from "@/components/molecules/evidence";
import { LayerTile, type LayerState } from "@/components/molecules/layer-tile";
import { TurnWaterfall } from "@/components/organisms/turn-waterfall";
import { LANGFUSE_TRACE_BASE } from "@/lib/api";
import { cn } from "@/lib/cn";
import { describeEvent, LAYER_BLURB, ROUTE_LABEL, t } from "@/lib/i18n";
import { LAYERS, ROUTE_ICON, ROUTE_TONE, STATUS_TONE, worstStatus } from "@/lib/layers";
import type { AgentMeta, Language, Layer, LayerEvent, TurnDone } from "@/lib/types";

export interface TurnTrace {
  turn: number;
  events: LayerEvent[];
  done?: TurnDone;
}

const num = (value: unknown): number | null => (typeof value === "number" ? value : null);
const pad2 = (n: number) => String(n).padStart(2, "0");
const formatMs = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

/** Estado de cada capa en un turno: LEARN es offline; la capa del último evento de un turno en curso, "corriendo". */
function layerStates(trace: TurnTrace | undefined): Record<Layer, LayerState> {
  const running = trace && !trace.done ? trace.events.at(-1)?.layer : undefined;
  return Object.fromEntries(
    LAYERS.map((layer) => {
      if (layer === "LEARN") return [layer, "offline"];
      if (layer === running) return [layer, "running"];
      return [layer, trace ? worstStatus(trace.events.filter((e) => e.layer === layer)) : "idle"];
    }),
  ) as Record<Layer, LayerState>;
}

/** La franja: las 7 capas del último turno, de un vistazo. Sin turnos, las figuras "respiran" en ola. */
function LayerStrip({ trace }: { trace: TurnTrace | undefined }) {
  const states = layerStates(trace);
  return (
    <div className="grid grid-cols-7 gap-[3px]">
      {LAYERS.map((layer, i) => (
        <LayerTile
          key={layer}
          layer={layer}
          state={states[layer]}
          caption={pad2(i + 1)}
          figureClassName={trace ? undefined : "animate-bob"}
          className="animate-pop"
          style={{ animationDelay: `${i * 50}ms` }}
        />
      ))}
    </div>
  );
}

/** Marca de advertencia o error: una figura sólida (triángulo / cuadrado), no un icono. */
function StatusMark({ status }: { status: LayerEvent["status"] }) {
  if (status === "warn") return <Shape kind="triangle" color="current" size={9} className="mt-[3px] text-warn" />;
  if (status === "error") return <Shape kind="square" color="current" size={8} className="mt-[4px] text-danger" />;
  return null;
}

function EventLine({ event, lang, meta }: { event: LayerEvent; lang: Language; meta: AgentMeta | null }) {
  const confidence = num(event.params.confidence);
  const languageConfidence = num(event.params.conf);
  const threshold = meta?.router_threshold;
  const attempts = num(event.params.max);
  return (
    <li className={cn("text-xs leading-snug", event.status === "error" ? "text-danger-ink" : event.status === "warn" ? "text-warn-ink" : "text-ink")}>
      <span className="flex items-start gap-1.5">
        <StatusMark status={event.status} />
        <span>{describeEvent(lang, event)}</span>
      </span>
      {event.code === "intent_classified" && confidence !== null && (
        <span className="mt-2 flex items-center gap-3">
          <BlockMeter
            value={confidence}
            threshold={threshold}
            tone={threshold === undefined || confidence >= threshold ? "brand" : "warn"}
            label={describeEvent(lang, event)}
            className="w-44"
          />
          {threshold !== undefined && (
            <span className="font-mono text-[10px] whitespace-nowrap text-ink-3">
              {t(lang, "threshold")} {Math.round(threshold * 100)}%
            </span>
          )}
        </span>
      )}
      {event.code === "language_detected" && languageConfidence !== null && (
        <BlockMeter value={languageConfidence} tone="accent" label={describeEvent(lang, event)} className="mt-2 w-44" />
      )}
      {event.code === "rule_applied" && typeof event.params.rule_id === "string" && (
        <span className="mt-2 block">
          <span className="mb-1.5 block font-mono text-[10px] tracking-[0.08em] text-ink-3 uppercase">{t(lang, "policyOrder")}</span>
          <PolicyLadder ruleId={event.params.rule_id} route={String(event.params.route)} />
        </span>
      )}
      {event.code === "clarification_requested" && attempts !== null && (
        <span className="mt-2 flex gap-1" aria-hidden>
          {Array.from({ length: attempts }, (_, i) => (
            <span key={i} className={cn("size-2.5", i < (num(event.params.attempt) ?? 0) ? "bg-warn" : "bg-surface-3")} />
          ))}
        </span>
      )}
    </li>
  );
}

/** Una tool call como línea de recibo: método, ruta, puntos guía, estado HTTP y tiempo. */
function ToolLine({ event }: { event: LayerEvent }) {
  const status = num(event.params.http_status);
  const attempt = num(event.params.attempt) ?? 1;
  const tone = status === null || status >= 500 ? "danger" : status >= 400 ? "warn" : "ok";
  return (
    <li className="flex items-baseline gap-2 font-mono text-[11px]">
      <span className={cn("w-9 shrink-0 font-bold", event.params.method === "GET" ? "text-ink-3" : "text-brand-ink")}>{String(event.params.method)}</span>
      <span className="min-w-0 truncate text-ink-2">{String(event.params.path)}</span>
      <span aria-hidden className="min-w-3 flex-1 translate-y-[-3px] border-b border-dotted border-line-strong" />
      {attempt > 1 && <span className="font-bold text-warn-ink">×{attempt}</span>}
      <span className={cn("font-bold", TONE_TEXT[tone])}>{status ?? "—"}</span>
      <span className="w-12 shrink-0 text-right text-ink-3 tabular-nums">{String(event.params.ms)} ms</span>
    </li>
  );
}

function LayerRow({ layer, state, events, lang, meta, index }: { layer: Layer; state: LayerState; events: LayerEvent[]; lang: Language; meta: AgentMeta | null; index: number }) {
  const [open, setOpen] = useState(false);
  const learn = layer === "LEARN";
  const empty = !learn && events.length === 0;
  const tools = events.filter((e) => e.code === "tool_call");
  const lines = events.filter((e) => e.code !== "tool_call");

  return (
    <li className="grid animate-rise grid-cols-[28px_1fr] gap-3 border-t border-line py-3 first:border-t-0" style={{ animationDelay: `${index * 40}ms` }}>
      <LayerTile layer={layer} state={state} size={28} className="mt-px" />
      <div className="min-w-0">
        <div className="flex min-h-7 items-center justify-between gap-2">
          <p title={LAYER_BLURB[lang][layer]} className={cn("font-mono text-[11px] font-bold tracking-[0.12em]", empty ? "text-ink-4" : "text-ink")}>
            {layer}
            {empty && <span className="ml-2 font-normal tracking-normal">—</span>}
          </p>
          {!learn && events.length > 0 && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              className={cn(
                "h-6 px-2 font-mono text-[10px] font-bold transition-colors",
                open ? "bg-ink text-on-ink" : "text-ink-3 ring-1 ring-line-strong ring-inset hover:text-ink hover:ring-ink-3",
              )}
            >
              {"{ } "}
              {open ? t(lang, "hideJson") : t(lang, "rawJson")}
            </button>
          )}
        </div>
        {learn && (
          <p className="text-xs text-ink-3">
            {t(lang, "learnOffline")}
            {meta ? ` · prompts ${meta.prompt_version}` : ""}
          </p>
        )}
        {lines.length > 0 && (
          <ul className="space-y-2">
            {lines.map((event, i) => (
              <EventLine key={i} event={event} lang={lang} meta={meta} />
            ))}
          </ul>
        )}
        {tools.length > 0 && (
          <ul className="mt-2.5 space-y-1 border-t border-dashed border-line pt-2">
            {tools.map((event, i) => (
              <ToolLine key={i} event={event} />
            ))}
          </ul>
        )}
        {open && <JsonView value={events} className="mt-2.5 rounded-none" />}
      </div>
    </li>
  );
}

/** Turno plegado: un cuadrado por capa con el color de su estado. */
function StateSquares({ states }: { states: Record<Layer, LayerState> }) {
  return (
    <span className="flex gap-[3px]" aria-hidden>
      {LAYERS.filter((l) => l !== "LEARN").map((layer) => {
        const state = states[layer];
        const fill = state === "idle" || state === "skipped" || state === "offline" ? "bg-surface-3" : state === "running" ? "bg-ink" : state === "ok" ? "bg-brand" : TONE_FILL[STATUS_TONE[state]];
        return <span key={layer} className={cn("size-2", fill)} />;
      })}
    </span>
  );
}

function TurnSection({ trace, lang, meta, open, onToggle }: { trace: TurnTrace; lang: Language; meta: AgentMeta | null; open: boolean; onToggle: () => void }) {
  const states = layerStates(trace);
  const route = trace.done?.route;
  return (
    <section className="animate-rise border-b border-line">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[auto_1fr_auto] items-end gap-4 px-5 pt-4 pb-4 text-left transition-colors hover:bg-surface"
      >
        <span>
          <span className="block font-mono text-[10px] tracking-[0.14em] text-ink-3 uppercase">{t(lang, "turn")}</span>
          <span className="block text-[40px] leading-[0.9] font-bold tracking-tight tabular-nums">{pad2(trace.turn)}</span>
        </span>
        <span className="flex flex-col items-start gap-2 pb-0.5">
          {route ? (
            <span className={cn("inline-flex h-6 items-center gap-1.5 px-2 text-[10px] font-bold tracking-[0.08em] uppercase", TONE_SOLID[ROUTE_TONE[route]])}>
              <Icon name={ROUTE_ICON[route]} size={12} strokeWidth={2.2} />
              {ROUTE_LABEL[lang][route]}
            </span>
          ) : (
            <span className="inline-flex h-6 items-center gap-1.5 bg-ink px-2 text-[10px] font-bold tracking-[0.08em] text-on-ink uppercase">
              <Shape kind="quarter" color="current" size={10} className="animate-orbit" />
              {t(lang, "running")}
            </span>
          )}
          {!open && <StateSquares states={states} />}
        </span>
        <span className="flex items-end gap-2">
          <span className="text-right">
            <span className="block font-mono text-[10px] tracking-[0.14em] text-ink-3 uppercase">{t(lang, "latencyShort")}</span>
            <span className="block text-2xl leading-none font-bold tabular-nums">{trace.done ? formatMs(trace.done.latency_ms) : "…"}</span>
          </span>
          <Icon name="chevron-down" size={16} className={cn("mb-0.5 text-ink-3 transition-transform duration-300", open && "rotate-180")} />
        </span>
      </button>
      {open && (
        <div className="animate-fade">
          <div className="border-t border-line px-5 py-4">
            <TurnWaterfall events={trace.events} lang={lang} />
          </div>
          <ul className="border-t border-line px-5 py-1">
            {LAYERS.map((layer, i) => (
              <LayerRow key={layer} layer={layer} state={states[layer]} events={trace.events.filter((e) => e.layer === layer)} lang={lang} meta={meta} index={i} />
            ))}
          </ul>
          {trace.done?.trace_id && LANGFUSE_TRACE_BASE && (
            <a
              href={`${LANGFUSE_TRACE_BASE}/${trace.done.trace_id}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between border-t border-line px-5 py-3 font-mono text-[11px] font-bold text-ink transition-colors hover:bg-surface"
            >
              <span>
                {t(lang, "viewTrace")} · <span className="font-normal text-ink-3">{trace.done.trace_id.slice(0, 12)}…</span>
              </span>
              <Icon name="external" size={13} />
            </a>
          )}
        </div>
      )}
    </section>
  );
}

/** Antes del primer mensaje: las 7 capas explicadas, cada una con su figura. */
function GlassEmpty({ lang }: { lang: Language }) {
  return (
    <div className="px-5 py-5">
      <p className="text-sm font-bold">{t(lang, "glassEmptyTitle")}</p>
      <p className="mt-1 text-xs leading-relaxed text-ink-3">{t(lang, "glassEmptyBody")}</p>
      <ol className="mt-4">
        {LAYERS.map((layer, i) => (
          <li key={layer} className="grid animate-rise grid-cols-[28px_1fr] items-center gap-3 border-t border-line py-2.5 first:border-t-0" style={{ animationDelay: `${i * 60}ms` }}>
            <LayerTile layer={layer} state={layer === "LEARN" ? "offline" : "ok"} size={28} />
            <span className="min-w-0">
              <span className="block font-mono text-[11px] font-bold tracking-[0.12em]">{layer}</span>
              <span className="block text-xs text-ink-3">{LAYER_BLURB[lang][layer]}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function GlassBox({ turns, lang, meta, onClose }: { turns: TurnTrace[]; lang: Language; meta: AgentMeta | null; onClose?: () => void }) {
  const ordered = [...turns].sort((a, b) => b.turn - a.turn);
  const latest = ordered[0];
  // El último turno se abre solo; los anteriores se pliegan salvo que el usuario los haya abierto.
  const [pinned, setPinned] = useState<Record<number, boolean>>({});
  const latency = [...turns]
    .filter((tr) => tr.done)
    .sort((a, b) => a.turn - b.turn)
    .map((tr) => ({ label: `${t(lang, "turn")} ${tr.turn}`, value: tr.done!.latency_ms }));

  return (
    <div data-theme="night" className="flex h-full flex-col overflow-hidden bg-bg text-ink">
      <header className="border-b border-line px-5 pt-5 pb-4">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[17px] leading-tight font-bold tracking-tight">{t(lang, "glassBox")}</p>
            <p className="mt-1 text-xs leading-snug text-ink-3">{t(lang, "glassBoxHint")}</p>
          </div>
          {onClose && <IconButton icon="x" label={t(lang, "close")} variant="ghost" onClick={onClose} className="lg:hidden" />}
        </div>
        <div className="mt-4">
          <LayerStrip trace={latest} />
        </div>
        {meta && (
          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10px] text-ink-3">
            <span title="purpose_version">
              purpose <span className="font-bold text-ink-2">{meta.purpose_version}</span>
            </span>
            <span aria-hidden>·</span>
            <span title="prompt_version">
              prompts <span className="font-bold text-ink-2">{meta.prompt_version}</span>
            </span>
            <span aria-hidden>·</span>
            <span title="model" className="font-bold text-ink-2">
              {meta.model}
            </span>
            <span aria-hidden>·</span>
            <span title="bank">
              bank <span className={cn("font-bold", meta.bank === "sim" ? "text-ok-ink" : "text-accent")}>{meta.bank}</span>
            </span>
            {!meta.auto_actions && <span className="bg-danger px-1.5 py-0.5 font-bold text-on-danger uppercase">kill switch</span>}
          </p>
        )}
        {latency.length > 1 && (
          <div className="mt-4 grid grid-cols-[auto_1fr] items-end gap-4">
            <span>
              <span className="block font-mono text-[10px] tracking-[0.14em] whitespace-nowrap text-ink-3 uppercase">{t(lang, "latency")}</span>
              <span className="block text-lg leading-tight font-bold tabular-nums">{formatMs(latency.at(-1)!.value)}</span>
            </span>
            <ColumnChart data={latency} height={40} label={`${t(lang, "latency")}: ${latency.map((p) => p.value).join(", ")} ms`} format={formatMs} />
          </div>
        )}
      </header>

      <div className="scrollbar-thin flex-1 overflow-y-auto">
        {ordered.length === 0 ? (
          <GlassEmpty lang={lang} />
        ) : (
          ordered.map((trace) => {
            const open = pinned[trace.turn] ?? trace.turn === latest?.turn;
            return (
              <TurnSection
                key={trace.turn}
                trace={trace}
                lang={lang}
                meta={meta}
                open={open}
                onToggle={() => setPinned((prev) => ({ ...prev, [trace.turn]: !open }))}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
