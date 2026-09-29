"use client";

import { useState } from "react";

import { Badge } from "@/components/atoms/badge";
import { Button } from "@/components/atoms/button";
import { DrawnCheck, Icon, type IconName } from "@/components/atoms/icon";
import { Card, Mono, Skeleton } from "@/components/atoms/primitives";
import { cn } from "@/lib/cn";
import { ageMinutes, sinceLabel } from "@/lib/handoff-meta";
import type { HandoffFeedback, HandoffFeedbackRecord } from "@/lib/types";

/** Campos de la ficha §9.4 que el agente puede marcar como faltantes (score `handoff_missing_fields`). */
export const FEEDBACK_FIELDS: { key: string; label: string }[] = [
  { key: "verified_facts", label: "Hechos verificados" },
  { key: "customer_claim", label: "Reclamo del cliente" },
  { key: "actions_taken", label: "Acciones tomadas" },
  { key: "open_questions", label: "Preguntas para el cliente" },
  { key: "risk_flags", label: "Señales de riesgo" },
  { key: "request_summary", label: "Resumen del pedido" },
];

const FIELD_LABEL = Object.fromEntries(FEEDBACK_FIELDS.map((f) => [f.key, f.label]));
const MAX_COMMENT = 500;

type Status = "idle" | "sending" | "sent" | "error";

function Header() {
  return (
    <div className="mb-3 flex items-center gap-2">
      <span className="grid size-7 place-items-center rounded-lg bg-accent text-on-accent">
        <Icon name="layer-learn" size={15} />
      </span>
      <h3 className="text-sm font-bold text-ink">¿La ficha te alcanzó?</h3>
      <Badge tone="accent" variant="solid" className="ml-auto">
        LEARN
      </Badge>
    </div>
  );
}

function Choice({
  selected,
  tone,
  icon,
  title,
  hint,
  onClick,
}: {
  selected: boolean;
  tone: "ok" | "warn";
  icon: IconName;
  title: string;
  hint: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={cn(
        "group flex items-start gap-2.5 rounded-2xl p-3 text-left ring-inset transition duration-200 ease-out-soft",
        selected
          ? tone === "ok"
            ? "bg-ok-soft ring-2 ring-ok"
            : "bg-warn-soft ring-2 ring-warn"
          : "bg-surface ring-[1.5px] ring-line hover:-translate-y-0.5 hover:ring-ink-3",
      )}
    >
      <span
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-lg transition-colors",
          selected ? (tone === "ok" ? "bg-ok text-white" : "bg-warn text-white") : "bg-surface-2 text-ink-3 group-hover:text-ink-2",
        )}
      >
        {selected ? <DrawnCheck size={14} /> : <Icon name={icon} size={16} />}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink">{title}</span>
        <span className="block text-[11px] leading-snug text-ink-3">{hint}</span>
      </span>
    </button>
  );
}

/**
 * LEARN: el agente humano califica la ficha. SIM guarda el feedback junto al handoff y, si la conversación
 * tiene traza, el agente la marca con los scores `handoff_quality` y `handoff_missing_fields` (valida MET-03).
 * `feedback === undefined` mientras se carga; `null` si todavía nadie la calificó.
 */
export function FeedbackForm({
  feedback,
  now,
  onSubmit,
}: {
  feedback: HandoffFeedbackRecord | null | undefined;
  now: number;
  onSubmit: (feedback: HandoffFeedback) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [useful, setUseful] = useState<boolean | null>(null);
  const [missing, setMissing] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  if (feedback === undefined) {
    return (
      <Card className="p-4">
        <Header />
        <Skeleton className="h-20 rounded-xl" />
      </Card>
    );
  }

  function startEditing(record: HandoffFeedbackRecord) {
    setUseful(record.useful);
    setMissing(record.missing_fields);
    setComment(record.comment ?? "");
    setStatus("idle");
    setEditing(true);
  }

  function toggle(key: string) {
    setMissing((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  async function submit() {
    if (useful === null) return;
    setStatus("sending");
    try {
      await onSubmit({ useful, missing_fields: useful ? [] : missing, comment: comment.trim() || null });
      setStatus("sent");
      setEditing(false);
    } catch {
      setStatus("error");
    }
  }

  if (feedback !== null && !editing) {
    return (
      <Card className="animate-rise p-4">
        <Header />
        <div className="flex items-start gap-3">
          <span
            className={cn(
              "grid size-9 shrink-0 place-items-center rounded-xl",
              feedback.useful ? "bg-ok-soft text-ok-ink" : "bg-warn-soft text-warn-ink",
            )}
          >
            {status === "sent" ? <DrawnCheck size={16} /> : <Icon name={feedback.useful ? "check-circle" : "alert-circle"} size={18} />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">{feedback.useful ? "La ficha alcanzó" : "A la ficha le faltó información"}</p>
            <p className="text-[11px] text-ink-3">
              <Mono>{feedback.reviewer_id}</Mono> · {sinceLabel(ageMinutes(feedback.submitted_at, now), "hace un momento")}
            </p>
            {feedback.missing_fields.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {feedback.missing_fields.map((key) => (
                  <Badge key={key} tone="warn" icon="circle-dashed">
                    {FIELD_LABEL[key] ?? key}
                  </Badge>
                ))}
              </div>
            )}
            {feedback.comment && (
              <blockquote className="mt-2 border-l-2 border-line-strong pl-3 text-xs leading-relaxed text-ink-2">{feedback.comment}</blockquote>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={() => startEditing(feedback)}>
            Cambiar
          </Button>
        </div>
        {status === "sent" && (
          <p className="mt-3 animate-fade text-[11px] text-ink-3">
            Guardado. Queda en la traza de la conversación como <Mono>handoff_quality</Mono>.
          </p>
        )}
      </Card>
    );
  }

  return (
    <Card className="animate-rise p-4">
      <Header />
      <div role="radiogroup" aria-label="¿La ficha te alcanzó?" className="grid gap-2 sm:grid-cols-2">
        <Choice selected={useful === true} tone="ok" icon="check-circle" title="Sí, me alcanzó" hint="Pude atender sin volver a preguntar" onClick={() => setUseful(true)} />
        <Choice selected={useful === false} tone="warn" icon="alert-circle" title="Le faltó algo" hint="Tuve que pedirle datos al cliente" onClick={() => setUseful(false)} />
      </div>

      {useful === false && (
        <fieldset className="mt-3 animate-slide-down">
          <legend className="mb-2 text-xs font-medium text-ink-2">¿Qué faltó?</legend>
          <div className="flex flex-wrap gap-1.5">
            {FEEDBACK_FIELDS.map((field) => {
              const on = missing.includes(field.key);
              return (
                <button
                  key={field.key}
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  onClick={() => toggle(field.key)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-inset transition duration-200",
                    on ? "bg-warn text-white ring-2 ring-warn" : "bg-surface text-ink-2 ring-[1.5px] ring-line hover:text-ink hover:ring-ink-3",
                  )}
                >
                  <Icon name={on ? "check" : "circle-dashed"} size={12} strokeWidth={on ? 2.4 : 1.75} />
                  {field.label}
                </button>
              );
            })}
          </div>
        </fieldset>
      )}

      <label className="mt-3 block">
        <span className="flex items-baseline justify-between text-xs font-medium text-ink-2">
          Comentario <span className="font-normal text-ink-4 tabular-nums">{comment.length}/{MAX_COMMENT}</span>
        </span>
        <textarea
          value={comment}
          maxLength={MAX_COMMENT}
          rows={2}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Opcional: qué te hubiera servido saber antes"
          className="mt-1.5 w-full resize-none rounded-2xl border-[1.5px] border-line-strong bg-surface px-3 py-2 text-sm text-ink transition outline-none placeholder:text-ink-4 hover:border-ink-3 focus:border-brand focus:ring-[3px] focus:ring-brand"
        />
      </label>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] text-ink-3">
          Va a la traza como score <Mono>handoff_quality</Mono>.
        </p>
        <div className="flex gap-2">
          {editing && (
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancelar
            </Button>
          )}
          <Button size="sm" icon="send" loading={status === "sending"} disabled={useful === null || (useful === false && missing.length === 0 && !comment.trim())} onClick={submit}>
            Enviar
          </Button>
        </div>
      </div>
      {status === "error" && (
        <p role="alert" className="mt-2 flex animate-shake items-center gap-1.5 text-xs text-danger-ink">
          <Icon name="alert-circle" size={13} /> No se pudo guardar. Intenta de nuevo.
        </p>
      )}
    </Card>
  );
}
