"use client";

// Composiciones con figuras sólidas: el friso que gira pieza por pieza, la figura de cada cliente demo y un
// grupo chico para esquinas. Todo es decorativo (aria-hidden) y se queda quieto con prefers-reduced-motion.
import { useEffect, useState } from "react";

import { FIGURE_BG, type FigureColor, Shape, type ShapeKind } from "@/components/atoms/shape";
import { cn } from "@/lib/cn";

// ───────────── friso ─────────────
const FRIEZE: { bg: FigureColor; fg: FigureColor; kind: ShapeKind }[] = [
  { bg: "cobalt", fg: "sun", kind: "quarter" },
  { bg: "ink", fg: "coral", kind: "half" },
  { bg: "sun", fg: "ink", kind: "quarter" },
  { bg: "mist", fg: "cobalt", kind: "arch" },
  { bg: "coral", fg: "paper", kind: "quarter" },
  { bg: "paper", fg: "ink", kind: "leaf" },
  { bg: "cobalt", fg: "paper", kind: "half" },
  { bg: "sun", fg: "coral", kind: "leaf" },
  { bg: "ink", fg: "sun", kind: "quarter" },
  { bg: "mist", fg: "coral", kind: "triangle" },
  { bg: "coral", fg: "ink", kind: "arch" },
  { bg: "paper", fg: "cobalt", kind: "quarter" },
  { bg: "ink", fg: "paper", kind: "leaf" },
  { bg: "cobalt", fg: "coral", kind: "arch" },
  { bg: "sun", fg: "cobalt", kind: "half" },
  { bg: "mist", fg: "ink", kind: "quarter" },
];

// Cuántas piezas se ven por ancho: 6 (móvil) · 8 (sm) · 12 (lg) · 16 (xl).
function visibility(i: number): string | false {
  if (i >= 12) return "hidden xl:block";
  if (i >= 8) return "hidden lg:block";
  if (i >= 6) return "hidden sm:block";
  return false;
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Friso de piezas: cada una gira un cuarto de vuelta, de a una, cada `every` ms; al pasar el cursor, la pieza gira.
 * Arranca con una disposición fija (igual en servidor y cliente) y solo después se mueve.
 */
export function FigureFrieze({ every = 1300, className }: { every?: number; className?: string }) {
  const [turns, setTurns] = useState<number[]>(() => FRIEZE.map((_, i) => (i * 3) % 4));
  const bump = (i: number) => setTurns((prev) => prev.map((t, j) => (j === i ? t + 1 : t)));

  useEffect(() => {
    if (reducedMotion()) return;
    const id = window.setInterval(() => bump(Math.floor(Math.random() * FRIEZE.length)), every);
    return () => window.clearInterval(id);
  }, [every]);

  return (
    <div aria-hidden className={cn("grid grid-cols-6 sm:grid-cols-8 lg:grid-cols-12 xl:grid-cols-16", className)}>
      {FRIEZE.map((tile, i) => (
        <div key={i} onPointerEnter={() => bump(i)} className={cn("relative aspect-square overflow-hidden", FIGURE_BG[tile.bg], visibility(i))}>
          <Shape
            kind={tile.kind}
            color={tile.fg}
            className="absolute inset-0 transition-transform duration-700 ease-spring"
            style={{ transform: `rotate(${turns[i] * 90}deg)` }}
          />
        </div>
      ))}
    </div>
  );
}

// ───────────── figura por cliente demo ─────────────
interface Piece {
  kind: ShapeKind | "morph";
  color: FigureColor;
  /** Posición y ancho dentro del recuadro (el alto sale de aspect-square). */
  box: string;
  /** Movimiento continuo cuando la tarjeta está elegida. */
  motion?: string;
  /** Transformación al pasar el cursor por la tarjeta (`group-hover:`). */
  hover?: string;
}

const CUSTOMER_FIGURES: { bg: FigureColor; pieces: Piece[] }[] = [
  {
    bg: "cobalt",
    pieces: [
      { kind: "circle", color: "sun", box: "right-[10%] -bottom-[16%] w-[50%]", motion: "animate-bob", hover: "group-hover:-translate-y-[14%]" },
      { kind: "square", color: "ink", box: "left-[12%] bottom-[16%] w-[16%]", hover: "group-hover:rotate-45" },
    ],
  },
  {
    bg: "coral",
    pieces: [
      { kind: "half", color: "ink", box: "left-[6%] -bottom-[25%] w-[60%]", motion: "animate-turn", hover: "group-hover:-translate-y-[12%]" },
      { kind: "circle", color: "paper", box: "right-[12%] top-[14%] w-[20%]", hover: "group-hover:scale-125" },
    ],
  },
  {
    bg: "mist",
    pieces: [
      { kind: "quarter", color: "cobalt", box: "left-0 top-0 w-[58%]", motion: "animate-turn", hover: "group-hover:rotate-90" },
      { kind: "square", color: "ink", box: "right-[12%] bottom-[14%] w-[18%]", hover: "group-hover:-translate-y-[25%]" },
    ],
  },
  {
    bg: "ink",
    pieces: [
      { kind: "arch", color: "coral", box: "left-[12%] -bottom-[4%] w-[40%]", hover: "group-hover:-translate-y-[8%]" },
      { kind: "circle", color: "sun", box: "right-[14%] top-[16%] w-[22%]", motion: "animate-bob", hover: "group-hover:scale-110" },
    ],
  },
  {
    bg: "sun",
    pieces: [
      { kind: "morph", color: "ink", box: "left-[36%] top-[20%] w-[30%]", motion: "animate-morph", hover: "group-hover:rotate-45" },
      { kind: "dot", color: "cobalt", box: "right-[8%] bottom-[8%] w-[22%]", hover: "group-hover:-translate-x-[30%]" },
    ],
  },
];

/** Recuadro con la figura de un cliente demo (el agente humano siempre usa el amarillo de "persona"). */
export function CustomerFigure({ variant, active = false, className }: { variant: number; active?: boolean; className?: string }) {
  const figure = CUSTOMER_FIGURES[variant % CUSTOMER_FIGURES.length];
  return (
    <span aria-hidden className={cn("relative block overflow-hidden", FIGURE_BG[figure.bg], className)}>
      {figure.pieces.map((piece, i) => (
        <span key={i} className={cn("absolute block aspect-square transition-transform duration-500 ease-spring", piece.box, piece.hover)}>
          {piece.kind === "morph" ? (
            <span className={cn("block size-full", FIGURE_BG[piece.color], active && piece.motion)} />
          ) : (
            <Shape kind={piece.kind} color={piece.color} className={active ? piece.motion : undefined} />
          )}
        </span>
      ))}
    </span>
  );
}

export const AGENT_FIGURE = 4;

// ───────────── grupo para esquinas ─────────────
/** Cuatro piezas en 2 × 2: una gira, otra sube, otra cambia de forma. */
export function FigureCluster({ size = 72, className }: { size?: number; className?: string }) {
  return (
    <span aria-hidden className={cn("grid shrink-0 grid-cols-2", className)} style={{ width: size, height: size }}>
      <span className="relative overflow-hidden bg-fig-cobalt">
        <Shape kind="quarter" color="sun" className="absolute inset-0 animate-turn" />
      </span>
      <span className="relative overflow-hidden bg-fig-paper">
        <span className="absolute inset-[18%]">
          <Shape kind="circle" color="coral" className="animate-bob" />
        </span>
      </span>
      <span className="relative overflow-hidden bg-fig-sun">
        <span className="absolute inset-[22%] animate-morph bg-fig-ink [animation-delay:-2s]" />
      </span>
      <span className="relative overflow-hidden bg-fig-ink">
        <Shape kind="half" color="cobalt" className="absolute inset-0 animate-turn [animation-delay:-3s]" />
      </span>
    </span>
  );
}
