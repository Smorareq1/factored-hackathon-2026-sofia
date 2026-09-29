import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Icon, type IconName } from "./icon";
import { TONE_OUTLINE, TONE_SOFT, TONE_SOLID, type Tone } from "./tone";

export interface BadgeProps {
  tone?: Tone;
  variant?: "soft" | "solid" | "outline";
  size?: "sm" | "md";
  icon?: IconName;
  mono?: boolean;
  className?: string;
  title?: string;
  children: ReactNode;
}

/** Etiqueta corta de estado o categoría. Nunca solo color: lleva texto y, si hace falta, icono. */
export function Badge({ tone = "neutral", variant = "soft", size = "sm", icon, mono, className, title, children }: BadgeProps) {
  const palette = variant === "solid" ? TONE_SOLID : variant === "outline" ? TONE_OUTLINE : TONE_SOFT;
  return (
    <span
      title={title}
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded-md font-semibold whitespace-nowrap",
        size === "sm" ? "h-6 px-2 text-[11px]" : "h-7 px-2.5 text-xs",
        mono && "font-mono tracking-tight",
        palette[tone],
        className,
      )}
    >
      {icon && <Icon name={icon} size={size === "sm" ? 12 : 14} strokeWidth={2} />}
      <span className="truncate">{children}</span>
    </span>
  );
}
