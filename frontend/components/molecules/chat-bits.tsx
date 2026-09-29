// Piezas del chat: burbujas, respuestas rápidas, aviso de transferencia, pista de capas y ruta.
import type { ReactNode } from "react";

import { SofiaAvatar } from "@/components/atoms/avatar";
import { Badge } from "@/components/atoms/badge";
import { Icon } from "@/components/atoms/icon";
import { Mono } from "@/components/atoms/primitives";
import { cn } from "@/lib/cn";
import { ROUTE_LABEL, t } from "@/lib/i18n";
import { LAYER_ICON, LAYERS, ROUTE_ICON, ROUTE_TONE } from "@/lib/layers";
import type { Handoff, Language, Layer, Route } from "@/lib/types";

export function CustomerBubble({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[85%] animate-rise self-end rounded-3xl rounded-br-md bg-ink px-4 py-2.5 text-[15px] leading-relaxed text-on-ink">
      {children}
    </div>
  );
}

export function AgentBubble({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-3xl rounded-tl-md bg-surface px-4 py-3 text-[15px] leading-relaxed whitespace-pre-line text-ink ring-1 ring-line ring-inset",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function QuickReplies({ replies, onReply }: { replies: string[]; onReply: (reply: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {replies.map((reply, i) => (
        <button
          key={reply}
          type="button"
          onClick={() => onReply(reply)}
          className={cn(
            "inline-flex h-10 animate-rise items-center gap-1.5 rounded-full px-4 text-sm font-semibold transition duration-200 ease-out-soft active:scale-95",
            i === 0
              ? "bg-brand text-white hover:bg-brand-strong"
              : "bg-surface text-ink ring-[1.5px] ring-line-strong ring-inset hover:ring-ink",
          )}
          style={{ animationDelay: `${260 + i * 80}ms` }}
        >
          {i === 0 && <Icon name="check" size={16} strokeWidth={2.2} />}
          {reply}
        </button>
      ))}
    </div>
  );
}

/** Transferencia a humano: bloque amarillo de "persona"; la línea punteada "fluye" de Sofía al agente. */
export function HandoffNotice({ handoff, lang }: { handoff: Handoff; lang: Language }) {
  return (
    <div className="animate-rise rounded-3xl bg-accent p-4 text-on-accent">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center">
          <SofiaAvatar size={34} />
          <svg width="58" height="14" viewBox="0 0 58 14" aria-hidden className="mx-1">
            <path d="M3 7h46" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="2 5" className="animate-flow" />
            <path d="m47 3 5 4-5 4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="inline-grid size-[34px] place-items-center rounded-full bg-on-accent text-accent" aria-hidden>
            <Icon name="headset" size={18} strokeWidth={2} />
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-bold">{t(lang, "handoffTitle")}</p>
          <p className="text-xs">
            {t(lang, "handoffRef")} <Mono className="font-bold">{handoff.handoff_id}</Mono>
          </p>
        </div>
      </div>
      <p className="mt-3 flex items-center gap-2 border-t border-on-accent/20 pt-3 text-xs">
        <Icon name="doc-off" size={14} />
        {t(lang, "handoffNote")}
      </p>
    </div>
  );
}

/** Las capas en línea: la activa respira, las que ya pasaron quedan encendidas. */
export function LayerTrack({ active, seen, size = 24 }: { active: Layer | null; seen: Layer[]; size?: number }) {
  const layers = LAYERS.filter((layer) => layer !== "LEARN");
  return (
    <ol className="flex items-center" aria-label={active ?? undefined}>
      {layers.map((layer, i) => {
        const isActive = layer === active;
        const isSeen = seen.includes(layer);
        return (
          <li key={layer} className="flex items-center">
            <span
              title={layer}
              className={cn(
                "grid place-items-center rounded-full transition-all duration-300 ease-out-soft",
                isActive ? "scale-110 animate-breathe bg-ink text-on-ink" : isSeen ? "bg-brand text-white" : "bg-surface-3 text-ink-4",
              )}
              style={{ width: size, height: size }}
            >
              <Icon name={LAYER_ICON[layer]} size={Math.round(size * 0.56)} />
            </span>
            {i < layers.length - 1 && (
              <span className={cn("h-[3px] w-2.5 transition-colors duration-300", isSeen ? "bg-brand" : "bg-surface-3")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function RouteBadge({ route, lang }: { route: Route | null | undefined; lang: Language }) {
  if (!route) return null;
  return (
    <Badge tone={ROUTE_TONE[route]} icon={ROUTE_ICON[route]}>
      {ROUTE_LABEL[lang][route]}
    </Badge>
  );
}
