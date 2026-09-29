import { cn } from "@/lib/cn";

export type Series = "series-1" | "series-2";

const FILL: Record<Series, string> = { "series-1": "bg-series-1", "series-2": "bg-series-2" };

export interface Segment {
  key: string;
  label: string;
  value: number;
  series: Series;
}

/** Barra 100 % con 2 px de aire entre segmentos y leyenda con valor y porcentaje (nunca solo color). */
export function SplitBar({ segments, label, className }: { segments: Segment[]; label: string; className?: string }) {
  const total = segments.reduce((sum, seg) => sum + seg.value, 0);
  const visible = segments.filter((seg) => seg.value > 0);
  return (
    <figure aria-label={label} className={cn("space-y-2.5", className)}>
      <div className="flex h-2.5 gap-[2px] overflow-hidden rounded-[4px] bg-surface-3">
        {visible.map((seg, i) => (
          <div
            key={seg.key}
            className={cn("h-full origin-left animate-grow-x", FILL[seg.series])}
            style={{ width: `${(seg.value / total) * 100}%`, animationDelay: `${i * 90}ms` }}
          />
        ))}
      </div>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {segments.map((seg) => (
          <span key={seg.key} className="flex items-center gap-1.5 text-ink-2">
            <span className={cn("size-2 rounded-[3px]", FILL[seg.series])} aria-hidden />
            {seg.label}
            <span className="font-semibold text-ink tabular-nums">{seg.value}</span>
            <span className="text-ink-3 tabular-nums">{total ? Math.round((seg.value / total) * 100) : 0}%</span>
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
