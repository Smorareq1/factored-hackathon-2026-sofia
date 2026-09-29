import type { CSSProperties } from "react";

import { cn } from "@/lib/cn";

/**
 * Figuras geométricas sólidas (círculo, medio círculo, cuarto, arco, cuadrado…) en una grilla de 100 × 100.
 * Son decorativas: nunca llevan significado solas. Se colorean con la paleta de figuras y se animan con
 * transform (girar, subir) o con las utilidades `animate-turn` / `animate-bob`.
 */
export type ShapeKind = "circle" | "half" | "quarter" | "arch" | "square" | "diamond" | "triangle" | "leaf" | "ring" | "dot";
export type FigureColor = "cobalt" | "sun" | "coral" | "ink" | "paper" | "mist";

export const FIGURE_TEXT: Record<FigureColor, string> = {
  cobalt: "text-fig-cobalt",
  sun: "text-fig-sun",
  coral: "text-fig-coral",
  ink: "text-fig-ink",
  paper: "text-fig-paper",
  mist: "text-fig-mist",
};

export const FIGURE_BG: Record<FigureColor, string> = {
  cobalt: "bg-fig-cobalt",
  sun: "bg-fig-sun",
  coral: "bg-fig-coral",
  ink: "bg-fig-ink",
  paper: "bg-fig-paper",
  mist: "bg-fig-mist",
};

const PATH: Record<ShapeKind, string> = {
  circle: "M50 0a50 50 0 1 1 0 100a50 50 0 1 1 0-100Z",
  // Diámetro sobre el borde inferior.
  half: "M0 100A50 50 0 0 1 100 100Z",
  // Centro en la esquina superior izquierda, radio = lado.
  quarter: "M0 0H100A100 100 0 0 1 0 100Z",
  arch: "M0 100V50A50 50 0 0 1 100 50V100Z",
  square: "M0 0H100V100H0Z",
  diamond: "M50 0L100 50L50 100L0 50Z",
  triangle: "M50 4L100 96H0Z",
  // Lente entre dos cuartos de círculo.
  leaf: "M0 100A100 100 0 0 1 100 0A100 100 0 0 1 0 100Z",
  ring: "M50 0a50 50 0 1 1 0 100a50 50 0 1 1 0-100Zm0 26a24 24 0 1 0 0 48a24 24 0 1 0 0-48Z",
  dot: "M50 30a20 20 0 1 1 0 40a20 20 0 1 1 0-40Z",
};

export function Shape({
  kind,
  color = "ink",
  size,
  rotate = 0,
  className,
  style,
}: {
  kind: ShapeKind;
  color?: FigureColor;
  /** Tamaño en px; sin `size`, ocupa su contenedor (w-full h-full). */
  size?: number;
  rotate?: number;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      aria-hidden
      focusable="false"
      className={cn("shrink-0 overflow-visible", size === undefined && "size-full", FIGURE_TEXT[color], className)}
      style={rotate ? { transform: `rotate(${rotate}deg)`, ...style } : style}
    >
      <path d={PATH[kind]} fill="currentColor" fillRule="evenodd" />
    </svg>
  );
}
