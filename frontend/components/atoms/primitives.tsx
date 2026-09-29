import type { HTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon, type IconName } from "./icon";

/** Rótulo pequeño en mayúsculas: encabeza secciones y grupos. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("text-[11px] font-semibold tracking-[0.1em] text-ink-3 uppercase", className)}>{children}</p>;
}

/** Dato técnico (IDs, rutas de API, versiones) en monoespaciada. */
export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[0.92em] tracking-tight", className)}>{children}</span>;
}

// Planos sólidos: se separan por color y por una línea fina, no por sombras difusas.
type CardVariant = "raised" | "flat" | "inset" | "night";
const CARD: Record<CardVariant, string> = {
  raised: "bg-surface ring-1 ring-line ring-inset",
  flat: "bg-surface",
  inset: "bg-surface-2",
  night: "bg-bg text-ink",
};

export function Card({ variant = "raised", className, ...rest }: HTMLAttributes<HTMLDivElement> & { variant?: CardVariant }) {
  return <div data-theme={variant === "night" ? "night" : undefined} className={cn("rounded-3xl", CARD[variant], className)} {...rest} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <span aria-hidden className={cn("shimmer block rounded-lg", className)} />;
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: IconName;
  invalid?: boolean;
}

export function Input({ icon, invalid, className, ...rest }: InputProps) {
  return (
    <span className="relative block">
      {icon && <Icon name={icon} size={18} className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2 text-ink-3" />}
      <input
        aria-invalid={invalid || undefined}
        className={cn(
          "h-12 w-full rounded-2xl border-[1.5px] bg-surface px-4 text-[15px] text-ink transition duration-200 outline-none",
          "placeholder:text-ink-4 focus:border-brand focus:ring-[3px] focus:ring-brand",
          invalid ? "border-danger ring-[3px] ring-danger" : "border-line-strong hover:border-ink-3",
          icon && "pl-11",
          className,
        )}
        {...rest}
      />
    </span>
  );
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cn("border-0 border-t border-line", className)} />;
}
