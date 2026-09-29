import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Tooltip de gráfica: tinta invertida del tema (oscuro sobre claro, claro sobre la caja de cristal). */
export function ChartTooltip({ x, y, children, className }: { x: number; y: number; children: ReactNode; className?: string }) {
  return (
    <div
      role="presentation"
      className={cn(
        "pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full animate-fade rounded-lg bg-ink px-2.5 py-1.5",
        "text-[11px] leading-tight font-medium whitespace-nowrap text-bg shadow-pop",
        className,
      )}
      style={{ left: x, top: y - 8 }}
    >
      {children}
    </div>
  );
}
