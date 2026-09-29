"use client";

// Caja de cristal (REQ-19): por turno, qué hizo cada una de las 7 capas. Se arma SOLO con eventos de capa
// (`code` + `params`); cada capa se expande a su JSON crudo para la defensa en vivo.
import { useState } from "react";

import { Badge } from "@/components/atoms/badge";
import { IconButton } from "@/components/atoms/button";
import { Icon, type IconName } from "@/components/atoms/icon";
import { Meter } from "@/components/atoms/meter";
import { Eyebrow } from "@/components/atoms/primitives";
import { Spinner } from "@/components/atoms/spinner";
import { TONE_FILL, TONE_SOFT, TONE_TEXT } from "@/components/atoms/tone";
import { Sparkline } from "@/components/molecules/charts/sparkline";
import { RouteBadge } from "@/components/molecules/chat-bits";
import { JsonView, PolicyLadder } from "@/components/molecules/evidence";
import { TurnWaterfall } from "@/components/organisms/turn-waterfall";
import { LANGFUSE_URL } from "@/lib/api";
import { cn } from "@/lib/cn";
import { describeEvent, LAYER_BLURB, t } from "@/lib/i18n";
import { LAYER_ICON, LAYERS, STATUS_TONE, worstStatus } from "@/lib/layers";
import type { AgentMeta, Language, Layer, LayerEvent, TurnDone } from "@/lib/types";

// Proyecto local de Langfuse (containers/local): sofia-local. En cloud, OPS define la URL del proyecto.
export const LANGFUSE_TRACE_BASE = LANGFUSE_URL ? `${LANGFUSE_URL}/project/sofia-local/traces` : null;

export interface TurnTrace {
  turn: number;
  events: LayerEvent[];
  done?: TurnDone;
}

const num = (value: unknown): number | null => (typeof value === "number" ? value : null);

function EventLine({ event, lang, meta }: { event: LayerEvent; lang: Language; meta: AgentMeta | null }) {
  const icon: IconName | null = event.status === "error" ? "alert-circle" : event.status === "warn" ? "shield-alert" : null;
  const confidence = num(event.params.confidence);
  const languageConfidence = num(event.params.conf);
  const threshold = meta?.router_threshold;
  return (
    <li className={cn("text-xs leading-snug", event.status === "error" ? "text-danger-ink" : event.status === "warn" ? "text-warn-ink" : "text-ink")}>
      <span className="flex items-start gap-1.5">
        {icon && <Icon name={icon} size={13} className="mt-px" />}
        <span>{describeEvent(lang, event)}</span>
      </span>
      {event.code === "intent_classified" && confidence !== null && (
        <span className="mt-1.5 flex items-center gap-2">
          <Meter
            value={confidence}
            threshold={threshold}
            tone={threshold === undefined || confidence >= threshold ? "brand" : "warn"}
            label={describeEvent(lang, event)}
            className="max-w-48"
          />
          {threshold !== undefined && (
            <span className="font-mono text-[10px] whitespace-nowrap text-ink-3">
              {t(lang, "threshold")} {Math.round(threshold * 100)}%
            </span>
          )}
        </span>
      )}
      {event.code === "language_detected" && languageConfidence !== null && (
        <Meter value={languageConfidence} tone="accent" label={describeEvent(lang, event)} className="mt-1.5 max-w-48" />
      )}
      {event.code === "rule_applied" && typeof event.params.rule_id === "string" && (
        <span className="mt-1.5 block">
          <span className="mb-1 block text-[10px] text-ink-3">{t(lang, "policyOrder")}</span>
          <PolicyLadder ruleId={event.params.rule_id} route={String(event.params.route)} />
        </span>
      )}
      {event.code === "clarification_requested" && num(event.params.max) !== null && (
        <span className="mt-1.5 flex gap-1" aria-hidden>
          {Array.from({ length: num(event.params.max)! }, (_, i) => (
            <span key={i} className={cn("h-1.5 w-5 rounded-full", i < (num(event.params.attempt) ?? 0) ? "bg-warn" : "bg-surface-3")} />
          ))}
        </span>
      )}
    </li>
  );
}

function ToolChip({ event }: { event: LayerEvent }) {
  const status = num(event.params.http_status);
  const attempt = num(event.params.attempt) ?? 1;
  const tone = status === null || status >= 500 ? "danger" : status >= 400 ? "warn" : "ok";
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-surface-2 px-1.5 py-1 font-mono text-[10px] text-ink-2 ring-1 ring-line ring-inset">
      <span className={cn("font-semibold", event.params.method === "GET" ? "text-info-ink" : "text-brand-ink")}>{String(event.params.method)}</span>
      <span className="truncate">{String(event.params.path)}</span>
      <span className={cn("font-semibold", TONE_TEXT[tone])}>{status ?? "—"}</span>
      <span className="text-ink-3">{String(event.params.ms)}ms</span>
      {attempt > 1 && <span className="text-warn-ink">×{attempt}</span>}
    </span>
  );
}

function LayerRow({ layer, events, lang, meta, index }: { layer: Layer; events: LayerEvent[]; lang: Language; meta: AgentMeta | null; index: number }) {
  const [open, setOpen] = useState(false);
  const learn = layer === "LEARN";
  const empty = !learn && events.length === 0;
  const tone = STATUS_TONE[learn ? "skipped" : worstStatus(events)];
  const tools = events.filter((e) => e.code === "tool_call");
  const lines = events.filter((e) => e.code !== "tool_call");

  return (
    <li className="animate-rise" style={{ animationDelay: `${index * 45}ms` }}>
      <div className={cn("flex gap-3 rounded-xl px-2 py-2 transition-colors", !empty && !learn && "hover:bg-surface-2")}>
        <span
          title={LAYER_BLURB[lang][layer]}
          className={cn(
            "relative mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ring-1 ring-line ring-inset",
            empty || learn ? "text-ink-4" : TONE_SOFT[tone],
          )}
        >
          <Icon name={LAYER_ICON[layer]} size={16} />
          {!empty && !learn && <span className={cn("absolute -top-0.5 -right-0.5 size-2 rounded-full ring-2 ring-bg", TONE_FILL[tone])} />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className={cn("font-mono text-[11px] font-semibold tracking-wider", empty ? "text-ink-4" : "text-ink-2")}>{layer}</p>
            {!learn && events.length > 0 && (
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10px] text-ink-3 transition-colors hover:bg-surface-3 hover:text-ink"
              >
                <Icon name="code" size={12} />
                {open ? t(lang, "hideJson") : t(lang, "rawJson")}
              </button>
            )}
          </div>
          {learn ? (
            <p className="text-xs text-ink-3">
              {t(lang, "learnOffline")}
              {meta ? ` · prompts ${meta.prompt_version}` : ""}
            </p>
          ) : empty ? (
            <p className="text-xs text-ink-4">—</p>
          ) : (
            <ul className="mt-1 space-y-1.5">
              {lines.map((event, i) => (
                <EventLine key={i} event={event} lang={lang} meta={meta} />
              ))}
            </ul>
          )}
          {tools.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {tools.map((event, i) => (
                <ToolChip key={i} event={event} />
              ))}
            </div>
          )}
          {open && <JsonView value={events} className="mt-2" />}
        </div>
      </div>
    </li>
  );
}

/** Resumen de un turno plegado: un punto por capa con el peor estado de sus eventos. */
function LayerDots({ events }: { events: LayerEvent[] }) {
  return (
    <span className="flex items-center gap-1" aria-hidden>
      {LAYERS.filter((l) => l !== "LEARN").map((layer) => {
        const status = worstStatus(events.filter((e) => e.layer === layer));
        return <span key={layer} className={cn("size-1.5 rounded-full", status === "idle" ? "bg-surface-3" : TONE_FILL[STATUS_TONE[status]])} />;
      })}
    </span>
  );
}

function TurnCard({ trace, lang, meta, open, onToggle }: { trace: TurnTrace; lang: Language; meta: AgentMeta | null; open: boolean; onToggle: () => void }) {
  return (
    <section className="animate-rise overflow-hidden rounded-3xl bg-surface">
      <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-surface-2">
        <span className="text-sm font-bold text-ink">
          {t(lang, "turn")} {trace.turn}
        </span>
        {trace.done ? <RouteBadge route={trace.done.route} lang={lang} /> : <Spinner size={14} className="text-brand" />}
        <span className="ml-auto flex items-center gap-2.5">
          {!open && <LayerDots events={trace.events} />}
          {trace.done && <span className="font-mono text-[11px] text-ink-3 tabular-nums">{trace.done.latency_ms} ms</span>}
          <Icon name="chevron-down" size={16} className={cn("text-ink-3 transition-transform duration-300", open && "rotate-180")} />
        </span>
      </button>
      {open && (
        <div className="animate-fade space-y-4 border-t border-line px-3 pt-3 pb-3">
          <TurnWaterfall events={trace.events} lang={lang} />
          <ul className="space-y-0.5">
            {LAYERS.map((layer, i) => (
              <LayerRow key={layer} layer={layer} events={trace.events.filter((e) => e.layer === layer)} lang={lang} meta={meta} index={i} />
            ))}
          </ul>
          {trace.done?.trace_id && LANGFUSE_TRACE_BASE && (
            <a
              href={`${LANGFUSE_TRACE_BASE}/${trace.done.trace_id}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-2 text-xs font-medium text-brand-ink hover:underline"
            >
              {t(lang, "viewTrace")} <Icon name="external" size={13} />
            </a>
          )}
        </div>
      )}
    </section>
  );
}

/** Antes del primer mensaje: las 7 capas explicadas (qué va a encenderse y por qué). */
function GlassEmpty({ lang }: { lang: Language }) {
  return (
    <div className="px-1 py-2">
      <p className="text-sm font-semibold text-ink">{t(lang, "glassEmptyTitle")}</p>
      <p className="mt-1 text-xs leading-relaxed text-ink-3">{t(lang, "glassEmptyBody")}</p>
      <ol className="mt-4 space-y-1.5">
        {LAYERS.map((layer, i) => (
          <li
            key={layer}
            className="flex animate-rise items-center gap-3 rounded-2xl bg-surface px-3 py-2.5"
            style={{ animationDelay: `${i * 70}ms` }}
          >
            <span className="grid size-8 place-items-center rounded-lg bg-surface-3 text-ink">
              <Icon name={LAYER_ICON[layer]} size={16} />
            </span>
            <span className="min-w-0">
              <span className="block font-mono text-[11px] font-semibold tracking-wider text-ink-2">{layer}</span>
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
  const latest = ordered[0]?.turn;
  // El último turno se abre solo; los anteriores se pliegan salvo que el usuario los haya abierto.
  const [pinned, setPinned] = useState<Record<number, boolean>>({});
  const latency = [...turns]
    .filter((tr) => tr.done)
    .sort((a, b) => a.turn - b.turn)
    .map((tr) => ({ label: `${t(lang, "turn")} ${tr.turn}`, value: tr.done!.latency_ms }));

  return (
    <div data-theme="night" className="relative flex h-full flex-col overflow-hidden bg-bg text-ink">

      <header className="relative border-b border-line px-5 pt-4 pb-4">
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand text-white">
            <Icon name="glass-box" size={20} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold">{t(lang, "glassBox")}</p>
            <p className="text-xs leading-snug text-ink-3">{t(lang, "glassBoxHint")}</p>
          </div>
          {onClose && <IconButton icon="x" label={t(lang, "close")} variant="ghost" onClick={onClose} className="lg:hidden" />}
        </div>
        {meta && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge mono icon="layer-purpose" title="purpose_version">
              {meta.purpose_version}
            </Badge>
            <Badge mono icon="code" title="prompt_version">
              {meta.prompt_version}
            </Badge>
            <Badge mono icon="activity" title="model">
              {meta.model}
            </Badge>
            <Badge mono icon="plug" tone={meta.bank === "sim" ? "ok" : "warn"} title="bank">
              bank:{meta.bank}
            </Badge>
            {!meta.auto_actions && (
              <Badge tone="danger" icon="ban">
                kill switch
              </Badge>
            )}
          </div>
        )}
        {latency.length > 0 && (
          <div className="mt-3 rounded-2xl bg-surface p-3">
            <div className="flex items-baseline justify-between">
              <Eyebrow>{t(lang, "latency")}</Eyebrow>
              <span className="font-mono text-xs font-semibold text-ink tabular-nums">{latency.at(-1)!.value} ms</span>
            </div>
            <Sparkline
              data={latency}
              height={44}
              label={`${t(lang, "latency")}: ${latency.map((p) => p.value).join(", ")} ms`}
              format={(v) => `${v} ms`}
            />
          </div>
        )}
      </header>

      <div className="scrollbar-thin relative flex-1 space-y-3 overflow-y-auto p-4">
        {ordered.length === 0 ? (
          <GlassEmpty lang={lang} />
        ) : (
          ordered.map((trace) => {
            const open = pinned[trace.turn] ?? trace.turn === latest;
            return (
              <TurnCard
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
