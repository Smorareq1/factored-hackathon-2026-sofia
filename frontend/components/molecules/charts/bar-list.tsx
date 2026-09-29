import { Icon, type IconName } from "@/components/atoms/icon";
import { cn } from "@/lib/cn";

export interface BarItem {
  key: string;
  label: string;
  value: number;
  icon?: IconName;
}

/** Barras horizontales de un solo tono, ordenadas, con el valor al final de cada fila (lista semántica). */
export function BarList({ items, label, limit = 4, className }: { items: BarItem[]; label: string; limit?: number; className?: string }) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const shown = sorted.slice(0, limit);
  const rest = sorted.slice(limit).reduce((sum, item) => sum + item.value, 0);
  const rows = rest > 0 ? [...shown, { key: "__other", label: "Otros", value: rest }] : shown;
  const max = Math.max(1, ...rows.map((r) => r.value));

  return (
    <ul aria-label={label} className={cn("space-y-2", className)}>
      {rows.map((row, i) => (
        <li key={row.key} className="group">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-1.5 text-ink-2">
              {"icon" in row && row.icon && <Icon name={row.icon} size={13} className="text-ink-3" />}
              <span className="truncate">{row.label}</span>
            </span>
            <span className="font-semibold text-ink tabular-nums">{row.value}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-r-[4px] bg-surface-3">
            <div
              className="h-full origin-left animate-grow-x rounded-r-[4px] bg-series-1 transition-opacity group-hover:opacity-80"
              style={{ width: `${(row.value / max) * 100}%`, animationDelay: `${i * 60}ms` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
