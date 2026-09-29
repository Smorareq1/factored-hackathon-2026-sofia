/** Marca de Sofía: una "S" de un solo trazo sobre un cuadrado cobalto, con un punto de sol. Colores sólidos. */
export function SofiaMark({ size = 36, animate = false, className }: { size?: number; animate?: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 40 40" width={size} height={size} className={className} aria-hidden focusable="false">
      <rect width="40" height="40" rx="11" style={{ fill: "var(--fig-cobalt)" }} />
      <path
        d="M25.6 14.4c-1-1.9-3.1-3.1-5.5-3.1-3.2 0-5.5 1.8-5.5 4.3 0 5.6 11.2 3.5 11.2 9.3 0 2.6-2.4 4.4-5.7 4.4-2.7 0-4.9-1.3-5.9-3.4"
        fill="none"
        stroke="#fff"
        strokeWidth="3.4"
        strokeLinecap="round"
        pathLength={1}
        className={animate ? "stroke-draw" : undefined}
      />
      <circle
        cx="31.5"
        cy="8.5"
        r="3.5"
        style={{ fill: "var(--fig-sun)" }}
        className={animate ? "origin-center animate-pop [animation-delay:700ms] [transform-box:fill-box]" : undefined}
      />
    </svg>
  );
}
