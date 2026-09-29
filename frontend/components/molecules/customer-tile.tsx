import { Flag } from "@/components/atoms/flag";
import { DrawnCheck, Icon } from "@/components/atoms/icon";
import { cn } from "@/lib/cn";
import type { DemoCustomer } from "@/lib/types";

import { AGENT_FIGURE, CustomerFigure } from "./figures";

/**
 * Cliente demo seleccionable: un recuadro de color sólido con su figura, y debajo nombre, documento y escenario.
 * La figura se mueve cuando la tarjeta está elegida. El agente humano lleva el amarillo de "persona".
 */
export function CustomerTile({ customer, selected, onSelect, index = 0 }: { customer: DemoCustomer; selected: boolean; onSelect: () => void; index?: number }) {
  const [name, ...meta] = customer.label.split(" · ");
  const agent = customer.role === "agent";
  const scenario = agent ? meta.join(" · ") : meta.slice(1).join(" · ");
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        "group relative flex h-full w-full animate-rise flex-col overflow-hidden rounded-3xl bg-surface text-left transition duration-300 ease-out-soft",
        "hover:-translate-y-1",
        selected ? "ring-[3px] ring-ink" : "ring-1 ring-line hover:ring-ink-3",
      )}
      style={{ animationDelay: `${160 + index * 70}ms` }}
    >
      <span className="relative block">
        <CustomerFigure variant={agent ? AGENT_FIGURE : index} active={selected} className="aspect-[5/3] w-full" />
        <span className="absolute top-2.5 left-2.5 inline-flex h-6 items-center gap-1.5 rounded-full bg-surface px-2 text-[11px] font-semibold text-ink">
          {agent ? <Icon name="headset" size={13} strokeWidth={2} /> : <Flag country={customer.country} size={11} />}
          {agent ? "Consola" : customer.country}
        </span>
        <span
          className={cn(
            "absolute top-2.5 right-2.5 grid size-6 place-items-center rounded-full bg-ink text-on-ink transition duration-300 ease-spring",
            selected ? "scale-100 opacity-100" : "scale-50 opacity-0",
          )}
        >
          {selected && <DrawnCheck size={12} />}
        </span>
      </span>
      <span className="flex flex-1 flex-col px-3.5 pt-3 pb-3.5">
        <span className="text-[15px] leading-tight font-bold tracking-tight text-ink">{name}</span>
        <span className="mt-0.5 font-mono text-[11px] text-ink-3">{customer.document_number}</span>
        {scenario && <span className="mt-1.5 line-clamp-2 text-xs leading-snug text-ink-2">{scenario}</span>}
      </span>
    </button>
  );
}
