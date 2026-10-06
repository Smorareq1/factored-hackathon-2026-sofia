"use client";

import { type ReactNode, useState } from "react";

import { Badge } from "@/components/atoms/badge";
import { DrawnCheck, Icon, type IconName } from "@/components/atoms/icon";
import { Card, Eyebrow, Mono } from "@/components/atoms/primitives";
import { RingGauge } from "@/components/molecules/charts/ring-gauge";
import { ActionRow, FactRow } from "@/components/molecules/evidence";
import { FeedbackForm } from "@/components/organisms/feedback-form";
import { LANGFUSE_TRACE_BASE } from "@/lib/api";
import { cn } from "@/lib/cn";
import { ageMinutes, completeness, reasonIcon, reasonTone, sinceLabel } from "@/lib/handoff-meta";
import { CLAIM_LABEL, FLAG_LABEL, REASON_LABEL } from "@/lib/i18n";
import type { Handoff, HandoffFeedback, HandoffFeedbackRecord } from "@/lib/types";

function Section({ title, icon, count, hint, children }: { title: string; icon: IconName; count?: number; hint?: string; children: ReactNode }) {
  return (
    <Card className="animate-rise p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid size-7 place-items-center rounded-lg bg-ink text-on-ink">
          <Icon name={icon} size={15} />
        </span>
        <h3 className="text-sm font-bold text-ink">{title}</h3>
        {count !== undefined && <span className="rounded-full bg-surface-3 px-1.5 text-[11px] font-semibold text-ink-2 tabular-nums">{count}</span>}
      </div>
      {hint && <p className="-mt-1.5 mb-3 text-xs text-ink-3">{hint}</p>}
      {children}
    </Card>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 rounded-xl border border-dashed border-line-strong px-3 py-2.5 text-xs text-ink-3">
      <Icon name="circle-dashed" size={14} className="shrink-0" />
      {children}
    </p>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label="Copiar ID"
      title="Copiar ID"
      onClick={() =>
        navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        })
      }
      className="grid size-6 place-items-center rounded-md text-ink-3 transition hover:bg-surface-3 hover:text-ink"
    >
      {copied ? <DrawnCheck size={13} className="text-ok" /> : <Icon name="copy" size={13} />}
    </button>
  );
}

/** Preguntas abiertas como checklist local: el agente las va tachando mientras habla con el cliente. */
function QuestionList({ questions }: { questions: string[] }) {
  const [asked, setAsked] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setAsked((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  return (
    <ul className="space-y-1.5">
      {questions.map((question, i) => {
        const done = asked.has(i);
        return (
          <li key={question}>
            <button
              type="button"
              role="checkbox"
              aria-checked={done}
              onClick={() => toggle(i)}
              className="flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm transition-colors hover:bg-surface-2"
            >
              <span
                className={cn(
                  "mt-0.5 grid size-[18px] shrink-0 place-items-center rounded-md border transition-colors duration-200",
                  done ? "border-brand bg-brand text-white" : "border-line-strong bg-surface",
                )}
              >
                {done && <DrawnCheck size={11} />}
              </span>
              <span className={cn("transition-colors", done ? "text-ink-3 line-through" : "text-ink")}>{question}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function HandoffSheet({
  handoff,
  now,
  feedback,
  onFeedback,
}: {
  handoff: Handoff;
  now: number;
  /** `undefined` mientras se carga; `null` si nadie la calificó todavía. */
  feedback: HandoffFeedbackRecord | null | undefined;
  onFeedback: (feedback: HandoffFeedback) => Promise<void>;
}) {
  const checks = completeness(handoff);
  const complete = checks.filter((c) => c.ok).length;
  const reason = handoff.reason_for_handoff;

  return (
    <article className="space-y-4">
      <Card variant="night" className="relative animate-rise overflow-hidden">
        <span aria-hidden className="absolute -right-10 -bottom-16 size-40 rounded-full bg-fig-sun" />
        <span aria-hidden className="absolute right-24 -bottom-8 size-16 bg-fig-cobalt" />
        <div className="relative flex flex-wrap items-start justify-between gap-5 p-6">
          <div className="min-w-0 flex-1 basis-80">
            <Eyebrow>Ficha de transferencia · §9.4</Eyebrow>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-ink-3">
              <Mono className="text-sm font-semibold text-ink-2">{handoff.handoff_id}</Mono>
              <CopyButton value={handoff.handoff_id} />
              <span>· {sinceLabel(ageMinutes(handoff.created_at, now))}</span>
            </div>
            <h2 className="mt-2 text-2xl leading-snug font-bold tracking-tight text-balance text-ink">{handoff.request_summary}</h2>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Badge size="md" tone={reasonTone(reason)} icon={reasonIcon(reason)}>
                {REASON_LABEL[reason] ?? reason}
              </Badge>
              {handoff.customer_claim && (
                <Badge size="md" icon="flag">
                  {CLAIM_LABEL[handoff.customer_claim] ?? handoff.customer_claim}
                </Badge>
              )}
              <Badge size="md" icon="globe" mono>
                {handoff.language.toUpperCase()}
              </Badge>
              <Badge size="md" icon="user" mono>
                {handoff.customer_id}
              </Badge>
              {handoff.system_version === "baseline" && (
                <Badge size="md" tone="accent" icon="bolt" title="Ficha creada por el baseline §8.7 (un LLM con tools, sin capas)">
                  Baseline
                </Badge>
              )}
              {handoff.authenticated ? (
                <Badge size="md" tone="ok" icon="shield-check">
                  OTP verificado
                </Badge>
              ) : (
                <Badge size="md" tone="warn" icon="shield-alert">
                  Sin autenticar
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-2xl bg-surface p-3 pr-4">
            <RingGauge value={complete} max={checks.length} tone={complete === checks.length ? "ok" : "brand"} label={`Completitud de la ficha: ${complete} de ${checks.length}`}>
              <span>
                <span className="text-lg font-semibold text-ink tabular-nums">{complete}</span>
                <span className="text-xs text-ink-3">/{checks.length}</span>
              </span>
            </RingGauge>
            <div>
              <Eyebrow>Completitud</Eyebrow>
              <ul className="mt-1 space-y-0.5">
                {checks.map((check) => (
                  <li key={check.label} className="flex items-center gap-1.5 text-[11px]">
                    <Icon name={check.ok ? "check" : "circle-dashed"} size={12} strokeWidth={2.4} className={check.ok ? "text-ok" : "text-ink-4"} />
                    <span className={check.ok ? "text-ink-2" : "text-ink-3"}>{check.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          <Section title="Hechos verificados" icon="shield-check" count={handoff.verified_facts.length} hint="Cada dato con la tool o la regla de la que salió.">
            {handoff.verified_facts.length === 0 ? (
              <Empty>La ficha no trae ningún dato con fuente: habrá que volver a consultarlo.</Empty>
            ) : (
              <ul className="space-y-1.5">
                {handoff.verified_facts.map((fact, i) => (
                  <FactRow key={`${fact.source}-${i}`} fact={fact.fact} source={fact.source} index={i} />
                ))}
              </ul>
            )}
          </Section>
          <Section title="Acciones tomadas" icon="layer-orchestrate" count={handoff.actions_taken.length}>
            {handoff.actions_taken.length === 0 && <Empty>No quedó registrada ninguna acción.</Empty>}
            <ol>
              {handoff.actions_taken.map((action, i) => (
                <ActionRow
                  key={`${action.action}-${i}`}
                  action={action.action}
                  result={action.result}
                  verified={action.verified}
                  last={i === handoff.actions_taken.length - 1}
                  index={i}
                />
              ))}
            </ol>
          </Section>
        </div>
        <div className="space-y-4">
          {handoff.open_questions.length > 0 && (
            <Section title="Preguntas para el cliente" icon="question" count={handoff.open_questions.length}>
              <QuestionList questions={handoff.open_questions} />
            </Section>
          )}
          {handoff.risk_flags.length > 0 && (
            <Section title="Señales de riesgo" icon="shield-alert">
              <div className="flex flex-wrap gap-1.5">
                {handoff.risk_flags.map((flag) => (
                  <Badge key={flag} tone="danger" size="md" icon="shield-alert" className="animate-pop" title={flag}>
                    {FLAG_LABEL[flag] ?? flag}
                  </Badge>
                ))}
              </div>
            </Section>
          )}
          <FeedbackForm feedback={feedback} now={now} onSubmit={onFeedback} />
          <Card variant="inset" className="flex animate-rise items-start gap-3 p-4 text-xs leading-relaxed text-ink-2">
            <Icon name="doc-off" size={20} className="mt-0.5 text-ink-3" />
            <p>
              <strong className="text-ink">Sin transcript, por diseño (REQ-05).</strong> La ficha trae hechos verificados con su fuente, no la
              conversación completa.
            </p>
          </Card>
          <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-[11px] text-ink-3">
            <span>
              schema <Mono>{handoff.schema_version}</Mono> · sistema <Mono>{handoff.system_version}</Mono>
            </span>
            {handoff.trace_id && LANGFUSE_TRACE_BASE && (
              <a
                href={`${LANGFUSE_TRACE_BASE}/${handoff.trace_id}`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-medium text-brand-ink hover:underline"
              >
                Ver traza <Icon name="external" size={12} />
              </a>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
