import type { SVGProps } from "react";

import { cn } from "@/lib/cn";

import { ICONS, type IconName } from "./icon-set";

export type { IconName } from "./icon-set";

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  /** Tamaño en px (tokens: 14 · 16 · 18 · 20 · 24). */
  size?: number;
  /** Si el icono comunica algo por sí solo; si no, queda oculto para lectores de pantalla. */
  label?: string;
}

export function Icon({ name, size = 18, label, strokeWidth = 1.75, className, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      className={cn("shrink-0", className)}
      {...rest}
    >
      {ICONS[name]}
    </svg>
  );
}

/** Check que se dibuja (confirmaciones y pasos completados). */
export function DrawnCheck({ size = 14, delay = 0, className }: { size?: number; delay?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden className={cn("shrink-0", className)}>
      <path
        d="m5 12.5 4.5 4.5L19 7.5"
        fill="none"
        stroke="currentColor"
        strokeWidth={3}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className="stroke-draw"
        style={{ animationDelay: `${delay}ms` }}
      />
    </svg>
  );
}
