import type { CSSProperties } from "react";

import { Shape } from "@/components/atoms/shape";
import { cn } from "@/lib/cn";
import { LAYER_SHAPE, type Status } from "@/lib/layers";
import type { Layer } from "@/lib/types";

/** Estado de una capa en la caja de cristal: el de sus eventos, o "corriendo" / "offline" (LEARN). */
export type LayerState = Status | "running" | "offline";

// Relleno sólido por estado; la figura y el rótulo usan el color de texto (currentColor).
const TILE: Record<LayerState, string> = {
  ok: "bg-brand text-on-brand",
  warn: "bg-accent text-on-accent",
  error: "bg-danger text-on-danger",
  running: "bg-ink text-on-ink",
  offline: "bg-surface-2 text-accent",
  skipped: "bg-surface-2 text-ink-4",
  idle: "bg-surface-2 text-ink-4",
};

// Las figuras simétricas no se ven girar: esas "saltan".
const SYMMETRIC = new Set(["circle", "ring", "square", "diamond"]);

/**
 * La figura de una capa sobre su color de estado. Con `size` es un cuadrado fijo; sin `size` llena el ancho
 * de su celda (la franja de la caja de cristal) y puede llevar el nombre de la capa adentro.
 */
export function LayerTile({
  layer,
  state,
  size,
  caption,
  className,
  style,
  figureClassName,
}: {
  layer: Layer;
  state: LayerState;
  size?: number;
  caption?: string;
  className?: string;
  style?: CSSProperties;
  figureClassName?: string;
}) {
  const kind = LAYER_SHAPE[layer];
  const motion = state === "running" ? (SYMMETRIC.has(kind) ? "animate-bob" : "animate-turn") : undefined;
  return (
    <span
      role="img"
      aria-label={`${layer}: ${state}`}
      title={`${layer} · ${state}`}
      className={cn("relative block shrink-0 overflow-hidden transition-colors duration-300", size === undefined && "aspect-square w-full", TILE[state], className)}
      style={size === undefined ? style : { width: size, height: size, ...style }}
    >
      <span className={cn("absolute left-1/2 block aspect-square w-[46%] -translate-x-1/2", caption ? "top-[18%]" : "top-1/2 -translate-y-1/2")}>
        <Shape kind={kind} color="current" className={cn(motion, figureClassName)} />
      </span>
      {caption && (
        <span className="absolute right-1 bottom-1 left-1.5 truncate font-mono text-[8px] leading-none font-bold tracking-[0.06em]">{caption}</span>
      )}
    </span>
  );
}
