"use client";

import type { ReactNode } from "react";

import { Icon, type IconName } from "@/components/atoms/icon";
import { Card, Eyebrow } from "@/components/atoms/primitives";
import { cn } from "@/lib/cn";
import { useCountUp } from "@/lib/hooks";

/** Indicador: rótulo, número que cuenta hasta su valor, bajada y (opcional) una gráfica chica. */
export function StatTile({
  label,
  value,
  format = (v) => String(Math.round(v)),
  sub,
  icon,
  children,
  className,
  index = 0,
}: {
  label: string;
  value?: number;
  format?: (value: number) => string;
  sub?: ReactNode;
  icon?: IconName;
  children?: ReactNode;
  className?: string;
  index?: number;
}) {
  const shown = useCountUp(value ?? 0);
  return (
    <Card className={cn("flex min-w-0 animate-rise flex-col gap-3 p-4", className)} style={{ animationDelay: `${index * 70}ms` }}>
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>{label}</Eyebrow>
        {icon && (
          <span className="grid size-7 place-items-center rounded-lg bg-ink text-on-ink">
            <Icon name={icon} size={15} />
          </span>
        )}
      </div>
      {value !== undefined && (
        <div className="flex items-baseline gap-2">
          <p className="text-4xl font-bold tracking-tight text-ink tabular-nums">{format(shown)}</p>
          {sub && <p className="text-xs text-ink-3">{sub}</p>}
        </div>
      )}
      {value === undefined && sub && <p className="text-xs text-ink-3">{sub}</p>}
      {children}
    </Card>
  );
}

export function EmptyState({ icon, title, body, children, className }: { icon: IconName; title: string; body?: string; children?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex animate-rise flex-col items-center text-center", className)}>
      <span className="relative grid size-16 place-items-center">
        <span aria-hidden className="absolute -top-1 -right-2 size-6 animate-bob rounded-full bg-fig-sun" />
        <span className="relative grid size-14 place-items-center rounded-2xl bg-ink text-on-ink">
          <Icon name={icon} size={26} />
        </span>
      </span>
      <p className="mt-4 text-base font-bold text-ink">{title}</p>
      {body && <p className="mt-1 max-w-sm text-sm leading-relaxed text-ink-3">{body}</p>}
      {children}
    </div>
  );
}
