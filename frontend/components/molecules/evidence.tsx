// Evidencia: hechos con su fuente, acciones con su verificación, la escalera de política y el JSON crudo.
import { Badge } from "@/components/atoms/badge";
import { DrawnCheck, Icon } from "@/components/atoms/icon";
import { TONE_SOLID, type Tone } from "@/components/atoms/tone";
import { cn } from "@/lib/cn";
import { POLICY_ORDER } from "@/lib/layers";
import type { JsonValue } from "@/lib/types";

export function sourceTone(source: string): Tone {
  if (source.startsWith("GET")) return "info";
  if (/^(POST|PUT|PATCH|DELETE)/.test(source)) return "brand";
  if (source.startsWith("POL")) return "accent";
  return "neutral";
}

/** De dónde salió el dato: endpoint de la API o regla de política. */
export function SourceChip({ source }: { source: string }) {
  return (
    <Badge tone={sourceTone(source)} icon={source.startsWith("POL") ? "layer-decide" : "plug"} mono title={source}>
      {source}
    </Badge>
  );
}

export function FactRow({ fact, source, index = 0 }: { fact: string; source: string; index?: number }) {
  return (
    <li
      className="flex animate-rise flex-wrap items-start justify-between gap-x-3 gap-y-1.5 rounded-xl bg-surface-2 px-3 py-2.5 text-sm ring-1 ring-line ring-inset"
      style={{ animationDelay: `${index * 45}ms` }}
    >
      <span className="flex min-w-0 items-start gap-2 text-ink">
        <Icon name="check" size={16} strokeWidth={2.2} className="mt-0.5 text-ok" />
        {fact}
      </span>
      <SourceChip source={source} />
    </li>
  );
}

/** Acción en una línea de tiempo: check dibujado si se verificó, círculo punteado si no. */
export function ActionRow({ action, result, verified, last, index = 0 }: { action: string; result: string; verified: boolean; last: boolean; index?: number }) {
  return (
    <li className="relative flex animate-rise gap-3 pb-4 last:pb-0" style={{ animationDelay: `${index * 70}ms` }}>
      {!last && <span aria-hidden className="absolute top-7 bottom-0 left-3 w-px bg-line" />}
      <span
        className={cn(
          "relative grid size-6 shrink-0 place-items-center rounded-full",
          verified ? "bg-ok text-white" : "bg-warn-soft text-warn-ink ring-[1.5px] ring-warn ring-inset",
        )}
      >
        {verified ? <DrawnCheck size={12} delay={200 + index * 120} /> : <Icon name="circle-dashed" size={14} />}
      </span>
      <div className="min-w-0 pt-0.5">
        <p className="text-sm font-semibold text-ink">{action}</p>
        <p className="font-mono text-xs break-all text-ink-3">{result}</p>
      </div>
    </li>
  );
}

const ROUTE_TONE: Record<string, Tone> = { auto: "ok", human: "info", escalate: "info", deny: "danger" };

/** Orden de evaluación de la política: las que pasaron, la que aplicó (encendida) y las que no se evaluaron. */
export function PolicyLadder({ ruleId, route }: { ruleId: string; route: string }) {
  const fired = POLICY_ORDER.indexOf(ruleId as (typeof POLICY_ORDER)[number]);
  return (
    <ol className="flex flex-wrap items-center gap-1">
      {POLICY_ORDER.map((rule, i) => {
        const state = fired < 0 ? "idle" : i < fired ? "passed" : i === fired ? "fired" : "skipped";
        return (
          <li key={rule} className="flex items-center">
            <span
              title={state}
              className={cn(
                "inline-flex h-6 items-center gap-1 rounded-[3px] px-1.5 font-mono text-[10px] font-bold",
                state === "passed" && "bg-surface-3 text-ink-3",
                state === "fired" && cn(TONE_SOLID[ROUTE_TONE[route] ?? "neutral"], "animate-pop px-2"),
                (state === "skipped" || state === "idle") && "text-ink-4 ring-1 ring-line-strong ring-inset",
              )}
              style={state === "fired" ? { animationDelay: `${i * 90}ms` } : undefined}
            >
              {state === "passed" && <Icon name="check" size={10} strokeWidth={2.6} />}
              {rule}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

const TOKEN = /("(?:\\.|[^"\\])*"(?:\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

/** JSON crudo con resaltado propio (claves, textos, números, literales). */
export function JsonView({ value, className }: { value: JsonValue | object; className?: string }) {
  const parts = JSON.stringify(value, null, 2).split(TOKEN);
  return (
    <pre
      className={cn(
        "scrollbar-thin max-h-72 animate-fade overflow-auto rounded-xl bg-bg p-3 font-mono text-[11px] leading-relaxed text-ink-2 ring-1 ring-line",
        className,
      )}
    >
      {parts.map((part, i) => {
        if (i % 2 === 0) return part;
        const style = part.endsWith(":")
          ? "text-accent-ink"
          : part.startsWith('"')
            ? "text-brand-ink"
            : /^(true|false|null)$/.test(part)
              ? "text-info-ink"
              : "text-warn-ink";
        return (
          <span key={i} className={style}>
            {part}
          </span>
        );
      })}
    </pre>
  );
}
