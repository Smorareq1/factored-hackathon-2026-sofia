// Set de iconos propio de Sofía DS: grilla de 24 px, trazo 1.75, puntas y uniones redondeadas, `currentColor`.
// Los puntos rellenos usan <Dot/>; todo lo demás es trazo, así el set se lee como una sola familia.
import type { ReactNode } from "react";

const Dot = ({ cx, cy, r = 1 }: { cx: number; cy: number; r?: number }) => (
  <circle cx={cx} cy={cy} r={r} fill="currentColor" stroke="none" />
);

export const ICONS = {
  // ── acciones ──
  send: (
    <>
      <path d="M20.5 3.5 3.9 10.1a.6.6 0 0 0 0 1.1l6.3 2.6 2.6 6.3a.6.6 0 0 0 1.1 0L20.5 3.5Z" />
      <path d="m10.2 13.8 4.7-4.7" />
    </>
  ),
  "chat-plus": (
    <>
      <path d="M20 11.5a7.5 7.5 0 0 1-10.9 6.7L4.5 19.5l1.3-4.3A7.5 7.5 0 1 1 20 11.5Z" />
      <path d="M12.5 8.6v5.8M9.6 11.5h5.8" />
    </>
  ),
  logout: (
    <>
      <path d="M9.5 20h-3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3" />
      <path d="m15.5 16.5 4.5-4.5-4.5-4.5M20 12H9.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.3-5.4" />
      <path d="M19.7 4.3v4h-4" />
    </>
  ),
  copy: (
    <>
      <rect x="8.5" y="8.5" width="11" height="11" rx="2" />
      <path d="M15.5 8.5v-2a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2" />
    </>
  ),
  external: (
    <>
      <path d="M13.5 4.5h6v6M19.5 4.5 11 13" />
      <path d="M18 14v3.5a2 2 0 0 1-2 2H6.5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2H10" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" />
    </>
  ),
  "arrow-right": <path d="M4.5 12h15M14 6.5l5.5 5.5-5.5 5.5" />,
  "chevron-down": <path d="m6 9 6 6 6-6" />,
  "chevron-right": <path d="m9 6 6 6-6 6" />,
  "chevron-left": <path d="m15 6-6 6 6 6" />,
  x: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,

  // ── estado ──
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  "check-circle": (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.2 2.4 2.4 4.8-4.8" />
    </>
  ),
  "circle-dashed": <circle cx="12" cy="12" r="8.5" strokeDasharray="2.6 2.9" />,
  "alert-circle": (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.8v4.6" />
      <Dot cx={12} cy={15.9} />
    </>
  ),
  question: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.7 9.6a2.4 2.4 0 0 1 4.6 1c0 1.6-2.3 2.1-2.3 3.4" />
      <Dot cx={12} cy={16.9} />
    </>
  ),
  "minus-circle": (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.5 12h7" />
    </>
  ),
  ban: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m6.1 6.1 11.8 11.8" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5M12 14.5v2" />
    </>
  ),
  shield: <path d="M12 3.2 5 5.8v5.6c0 4.2 2.9 7.6 7 9.4 4.1-1.8 7-5.2 7-9.4V5.8l-7-2.6Z" />,
  "shield-check": (
    <>
      <path d="M12 3.2 5 5.8v5.6c0 4.2 2.9 7.6 7 9.4 4.1-1.8 7-5.2 7-9.4V5.8l-7-2.6Z" />
      <path d="m9 12 2.2 2.2L15.2 10" />
    </>
  ),
  "shield-alert": (
    <>
      <path d="M12 3.2 5 5.8v5.6c0 4.2 2.9 7.6 7 9.4 4.1-1.8 7-5.2 7-9.4V5.8l-7-2.6Z" />
      <path d="M12 8.3v4.2" />
      <Dot cx={12} cy={15.6} />
    </>
  ),
  flag: <path d="M6 20.5v-16h11.5l-2.2 4.2 2.2 4.3H6" />,

  // ── dominio ──
  key: (
    <>
      <circle cx="8" cy="15.5" r="3.8" />
      <path d="m10.8 12.8 8.7-8.7M16.5 7.3l2.3 2.3M14.2 9.6l1.8 1.8" />
    </>
  ),
  "id-card": (
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2.2" />
      <circle cx="9" cy="11" r="2" />
      <path d="M6.2 15.5c.5-1.3 1.6-2 2.8-2s2.3.7 2.8 2M14 10h3.5M14 13h3.5" />
    </>
  ),
  message: (
    <>
      <path d="M5.5 4.5h13a2 2 0 0 1 2 2V15a2 2 0 0 1-2 2H11l-4.6 3.4V17h-.9a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2Z" />
      <path d="M8 9h8M8 12.3h5" />
    </>
  ),
  phone: (
    <>
      <rect x="6.5" y="3" width="11" height="18" rx="2.5" />
      <path d="M10.5 17.8h3" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.5" r="3.7" />
      <path d="M4.8 20c.9-3.7 3.8-5.8 7.2-5.8s6.3 2.1 7.2 5.8" />
    </>
  ),
  headset: (
    <>
      <path d="M4.5 13.5V12a7.5 7.5 0 0 1 15 0v1.5" />
      <path d="M4.5 13.5a1 1 0 0 1 1-1H7a1 1 0 0 1 1 1V17a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1Z" />
      <path d="M19.5 13.5a1 1 0 0 0-1-1H17a1 1 0 0 0-1 1V17a1 1 0 0 0 1 1h1.5a1 1 0 0 0 1-1Z" />
      <path d="M18.5 18c0 1.4-1.6 2.5-4.5 2.5" />
    </>
  ),
  transfer: <path d="M4.5 8.5h14L15 5M19.5 15.5h-14L9 19" />,
  "doc-off": (
    <>
      <path d="M7 3.5h6.5L18 8v10.5a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z" />
      <path d="M13.5 3.5V8H18M8.5 12.5h6M8.5 15.5h3.5M3.5 3.5l17 17" />
    </>
  ),
  inbox: (
    <>
      <path d="M3.8 13.2 6.2 6a1.6 1.6 0 0 1 1.5-1.1h8.6a1.6 1.6 0 0 1 1.5 1.1l2.4 7.2v4.9a1.7 1.7 0 0 1-1.7 1.7H5.5a1.7 1.7 0 0 1-1.7-1.7Z" />
      <path d="M3.8 13.2h4.4l1.3 2.3h5l1.3-2.3h4.4" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5s1.1-6.1 3.4-8.5Z" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  bolt: <path d="M13.2 3.5 5.5 13h6l-.7 7.5L18.5 11h-6l.7-7.5Z" />,
  activity: <path d="M3.5 12.5h3.8l2.4-6.5 4.3 12 2.4-5.5h4.1" />,
  card: (
    <>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2.2" />
      <path d="M3.5 9.5h17M7 14.5h3.5" />
    </>
  ),
  store: (
    <>
      <path d="M4.5 9.2 6 4.5h12l1.5 4.7" />
      <path d="M4.5 9.2a2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0 5 0" />
      <path d="M5.5 11.3v8.2h13v-8.2M10 19.5v-4h4v4" />
    </>
  ),
  calendar: (
    <>
      <rect x="4" y="5.5" width="16" height="14.5" rx="2.2" />
      <path d="M4 10h16M8.5 3.5V7M15.5 3.5V7" />
      <Dot cx={8.5} cy={14.2} r={0.9} />
      <Dot cx={12} cy={14.2} r={0.9} />
    </>
  ),
  receipt: (
    <>
      <path d="M6.5 3.5h11v17l-1.8-1.2-1.9 1.2-1.8-1.2-1.8 1.2-1.9-1.2-1.8 1.2Z" />
      <path d="M9.5 8h5M9.5 11.5h5M9.5 15h3" />
    </>
  ),
  plug: (
    <>
      <path d="M9 3.5v4M15 3.5v4" />
      <path d="M6.5 7.5h11v3a5.5 5.5 0 0 1-11 0v-3Z" />
      <path d="M12 16v4.5" />
    </>
  ),
  code: <path d="m8.5 8-4 4 4 4M15.5 8l4 4-4 4M13.4 5.5l-2.8 13" />,
  sparkle: (
    <>
      <path d="M11 3.5c.5 3.9 2.1 5.5 6 6-3.9.5-5.5 2.1-6 6-.5-3.9-2.1-5.5-6-6 3.9-.5 5.5-2.1 6-6Z" />
      <path d="M18 14.5c.2 1.6.9 2.3 2.5 2.5-1.6.2-2.3.9-2.5 2.5-.2-1.6-.9-2.3-2.5-2.5 1.6-.2 2.3-.9 2.5-2.5Z" />
    </>
  ),
  palette: (
    <>
      <path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.2 0 1.8-.9 1.4-2l-.3-.8c-.4-1.1.3-2.2 1.5-2.2H17a3.5 3.5 0 0 0 3.5-3.5c0-4.8-3.8-8.5-8.5-8.5Z" />
      <Dot cx={7.8} cy={11.6} />
      <Dot cx={9.9} cy={7.6} />
      <Dot cx={14.4} cy={7.5} />
    </>
  ),
  // Caja de cristal: un cubo con las aristas ocultas a la vista (punteadas).
  "glass-box": (
    <>
      <path d="M12 3 20 7.5v9L12 21l-8-4.5v-9L12 3Z" />
      <path d="M4 7.5 12 12l8-4.5M12 12v9" />
      <path d="M12 12V3.6M12 12l7.4 4.2M12 12l-7.4 4.2" strokeDasharray="1.2 2.2" opacity=".55" />
    </>
  ),

  // ── las 7 capas ──
  "layer-purpose": (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.6" />
      <Dot cx={12} cy={12} r={1.4} />
    </>
  ),
  "layer-sense": (
    <>
      <circle cx="12" cy="12" r="1.8" />
      <path d="M8.4 8.4a5.1 5.1 0 0 0 0 7.2M15.6 8.4a5.1 5.1 0 0 1 0 7.2M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8" />
    </>
  ),
  "layer-interpret": (
    <>
      <path d="M4 8.5v-2a2 2 0 0 1 2-2h2.5M15.5 4.5H18a2 2 0 0 1 2 2v2M20 15.5v2a2 2 0 0 1-2 2h-2.5M8.5 19.5H6a2 2 0 0 1-2-2v-2" />
      <path d="M8 10h8M8 14h5" />
    </>
  ),
  "layer-decide": (
    <>
      <path d="M12 20.5V14M12 14 6.8 8.8M12 14l5.2-5.2" />
      <path d="M6.5 12.3V8.5h3.8M17.5 12.3V8.5h-3.8" />
    </>
  ),
  "layer-orchestrate": (
    <>
      <rect x="3.5" y="3.5" width="6" height="6" rx="1.6" />
      <rect x="14.5" y="14.5" width="6" height="6" rx="1.6" />
      <circle cx="17.5" cy="6.5" r="2.6" />
      <path d="M9.5 6.5h5.4M6.5 9.5V15a2.5 2.5 0 0 0 2.5 2.5h5.5" />
    </>
  ),
  "layer-learn": (
    <>
      <path d="M19.5 12a7.5 7.5 0 0 1-13.1 5M4.5 12a7.5 7.5 0 0 1 13.1-5" />
      <path d="M17.8 3.8v3.4h-3.4M6.2 20.2v-3.4h3.4" />
    </>
  ),
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof ICONS;
export const ICON_NAMES = Object.keys(ICONS) as IconName[];
