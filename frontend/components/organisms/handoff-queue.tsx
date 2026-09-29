"use client";

import { useState } from "react";

import { Badge } from "@/components/atoms/badge";
import { Icon } from "@/components/atoms/icon";
import { Eyebrow } from "@/components/atoms/primitives";
import { TONE_SOLID } from "@/components/atoms/tone";
import { Segmented } from "@/components/molecules/segmented";
import { EmptyState } from "@/components/molecules/stat-tile";
import { cn } from "@/lib/cn";
import { ageMinutes, formatAge, reasonIcon, reasonTone } from "@/lib/handoff-meta";
import { FLAG_LABEL, REASON_LABEL } from "@/lib/i18n";
import type { Handoff } from "@/lib/types";

type Filter = "all" | "es" | "pt";

function QueueItem({ handoff, selected, fresh, now, index, onSelect }: { handoff: Handoff; selected: boolean; fresh: boolean; now: number; index: number; onSelect: () => void }) {
  const reason = handoff.reason_for_handoff;
  const extra = handoff.risk_flags.length - 2;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected || undefined}
      className={cn(
        "relative w-full animate-rise overflow-hidden rounded-2xl p-3 text-left transition duration-200 ease-out-soft",
        selected ? "bg-surface ring-2 ring-ink ring-inset" : "hover:bg-surface",
      )}
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <span aria-hidden className={cn("absolute inset-y-0 left-0 w-1.5 bg-brand transition-transform duration-300 ease-spring", selected ? "scale-y-100" : "scale-y-0")} />
      <span className="flex items-center gap-2.5">
        <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg", TONE_SOLID[reasonTone(reason)])}>
          <Icon name={reasonIcon(reason)} size={16} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-mono text-xs font-bold text-ink">{handoff.handoff_id}</span>
          <span className="block truncate text-[11px] text-ink-3">{REASON_LABEL[reason] ?? reason}</span>
        </span>
        {fresh ? (
          <Badge tone="brand" variant="solid" className="animate-pop">
            nuevo
          </Badge>
        ) : (
          <span className="flex items-center gap-1 text-[11px] text-ink-3 tabular-nums">
            <Icon name="clock" size={12} />
            {formatAge(ageMinutes(handoff.created_at, now))}
          </span>
        )}
      </span>
      <span className="mt-2 line-clamp-2 block text-xs leading-relaxed text-ink-2">{handoff.request_summary}</span>
      <span className="mt-2 flex flex-wrap gap-1">
        <Badge mono>{handoff.language.toUpperCase()}</Badge>
        {handoff.risk_flags.slice(0, 2).map((flag) => (
          <Badge key={flag} tone="danger" icon="shield-alert">
            {FLAG_LABEL[flag] ?? flag}
          </Badge>
        ))}
        {extra > 0 && <Badge>+{extra}</Badge>}
      </span>
    </button>
  );
}

export function HandoffQueue({
  queue,
  selectedId,
  fresh,
  now,
  onSelect,
}: {
  queue: Handoff[];
  selectedId: string | null;
  fresh: Set<string>;
  now: number;
  onSelect: (id: string) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = queue.filter((h) => filter === "all" || h.language === filter);
  return (
    <nav aria-label="Cola de handoffs" className="flex h-full min-h-0 flex-col">
      <div className="flex items-end justify-between gap-2 px-4 pt-4 pb-3">
        <div>
          <Eyebrow>Cola</Eyebrow>
          <p className="text-sm font-semibold text-ink">
            {queue.length} {queue.length === 1 ? "caso" : "casos"}
          </p>
        </div>
        <Segmented
          value={filter}
          onChange={setFilter}
          label="Filtrar por idioma"
          options={[
            { value: "all", label: "Todos" },
            { value: "es", label: "ES" },
            { value: "pt", label: "PT" },
          ]}
        />
      </div>
      <ul className="scrollbar-thin flex-1 space-y-1 overflow-y-auto px-2 pb-4">
        {shown.map((handoff, i) => (
          <li key={handoff.handoff_id}>
            <QueueItem
              handoff={handoff}
              selected={handoff.handoff_id === selectedId}
              fresh={fresh.has(handoff.handoff_id)}
              now={now}
              index={i}
              onSelect={() => onSelect(handoff.handoff_id)}
            />
          </li>
        ))}
        {shown.length === 0 && (
          <li className="px-4 py-10">
            <EmptyState icon="inbox" title="La cola está vacía" body="Cuando Sofía transfiera un caso, aparece aquí con su ficha." />
          </li>
        )}
      </ul>
    </nav>
  );
}
