"use client";

import { BarList } from "@/components/molecules/charts/bar-list";
import { ColumnChart } from "@/components/molecules/charts/column-chart";
import { SplitBar } from "@/components/molecules/charts/split-bar";
import { StatTile } from "@/components/molecules/stat-tile";
import { ageMinutes, formatAge, reasonIcon } from "@/lib/handoff-meta";
import { FLAG_LABEL, REASON_LABEL } from "@/lib/i18n";
import type { Handoff } from "@/lib/types";

function countBy(values: string[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return counts;
}

/** Tablero de la cola: volumen y llegadas, motivos, idioma y señales de riesgo. */
export function QueueOverview({ queue, now }: { queue: Handoff[]; now: number }) {
  const ages = queue.map((h) => ageMinutes(h.created_at, now));
  const oldest = ages.length ? Math.max(...ages) : 0;
  // Llegadas de la última hora en 12 franjas de 5 minutos (la última es "ahora").
  const arrivals = Array.from({ length: 12 }, (_, i) => {
    const to = 60 - i * 5;
    const from = to - 5;
    return {
      label: from === 0 ? "últimos 5 min" : `hace ${from}–${to} min`,
      value: ages.filter((age) => age >= from && age < to).length,
    };
  });
  const reasons = [...countBy(queue.map((h) => h.reason_for_handoff))].map(([key, value]) => ({
    key,
    value,
    label: REASON_LABEL[key] ?? key,
    icon: reasonIcon(key),
  }));
  const flags = [...countBy(queue.flatMap((h) => h.risk_flags))].map(([key, value]) => ({ key, value, label: FLAG_LABEL[key] ?? key }));
  const spanish = queue.filter((h) => h.language === "es").length;
  const authenticated = queue.filter((h) => h.authenticated).length;

  return (
    <section aria-label="Resumen de la cola" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label="En cola" value={queue.length} icon="inbox" sub={queue.length ? `más antigua: ${formatAge(oldest)}` : "sin casos"} index={0}>
        <ColumnChart data={arrivals} height={52} label="Llegadas en la última hora, por franjas de 5 minutos" />
      </StatTile>
      <StatTile label="Motivo de transferencia" icon="flag" index={1}>
        {reasons.length ? <BarList items={reasons} label="Casos por motivo" limit={3} /> : <p className="text-xs text-ink-3">Sin casos todavía.</p>}
      </StatTile>
      <StatTile label="Idioma del cliente" icon="globe" index={2}>
        <SplitBar
          label="Casos por idioma"
          segments={[
            { key: "es", label: "Español", value: spanish, series: "series-1" },
            { key: "pt", label: "Português", value: queue.length - spanish, series: "series-2" },
          ]}
        />
        <p className="text-xs text-ink-3">
          Autenticados con OTP:{" "}
          <span className="font-semibold text-ink tabular-nums">
            {authenticated}/{queue.length}
          </span>
        </p>
      </StatTile>
      <StatTile label="Señales de riesgo" icon="shield-alert" index={3}>
        {flags.length ? <BarList items={flags} label="Señales de riesgo en la cola" limit={3} /> : <p className="text-xs text-ink-3">Ningún caso con señales de riesgo.</p>}
      </StatTile>
    </section>
  );
}
