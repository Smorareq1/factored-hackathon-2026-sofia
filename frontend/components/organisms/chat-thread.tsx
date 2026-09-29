"use client";

import { useEffect, useRef } from "react";

import { SofiaAvatar } from "@/components/atoms/avatar";
import { Icon } from "@/components/atoms/icon";
import { SofiaMark } from "@/components/atoms/logo";
import { Eyebrow } from "@/components/atoms/primitives";
import { type FigureColor, Shape, type ShapeKind } from "@/components/atoms/shape";
import { CaseReceipt } from "@/components/molecules/case-receipt";
import { AgentBubble, CustomerBubble, HandoffNotice, LayerTrack, QuickReplies } from "@/components/molecules/chat-bits";
import { CandidateOption, TransactionTicket } from "@/components/molecules/transaction-card";
import { LAYER_DOING, SUGGESTIONS, t } from "@/lib/i18n";
import type { AgentMessage, Handoff, Language, Layer } from "@/lib/types";

export interface ChatItem {
  id: string;
  role: "customer" | "agent" | "error";
  text: string;
  turn: number;
  message?: AgentMessage;
  handoff?: Handoff;
}

// El texto trae las opciones también en texto (el harness solo lee texto); en la UI ya son tarjetas.
const OPTION_LINE = /^(Opción|Opção) \d+:/;

function visibleText(item: ChatItem): string {
  if (!item.message?.candidates.length) return item.text;
  return item.text
    .split("\n")
    .filter((line) => !OPTION_LINE.test(line.trim()))
    .join("\n")
    .trim();
}

const BULLETS: { kind: ShapeKind; color: FigureColor }[] = [
  { kind: "circle", color: "cobalt" },
  { kind: "square", color: "coral" },
  { kind: "triangle", color: "ink" },
  { kind: "half", color: "cobalt" },
];

/** Cuatro piezas que entran de a una: la marca y tres figuras que se mueven. */
function WelcomeFigure() {
  const tile = "relative size-12 animate-pop overflow-hidden rounded-2xl sm:size-14";
  return (
    <div aria-hidden className="flex gap-2">
      <SofiaMark size={56} className="size-12 animate-pop sm:size-14" />
      <span className={`${tile} bg-fig-sun [animation-delay:90ms]`}>
        <Shape kind="quarter" color="ink" className="absolute inset-0 animate-turn" />
      </span>
      <span className={`${tile} bg-fig-ink [animation-delay:180ms]`}>
        <span className="absolute inset-[22%]">
          <Shape kind="circle" color="coral" className="animate-bob" />
        </span>
      </span>
      <span className={`${tile} bg-fig-mist [animation-delay:270ms]`}>
        <Shape kind="half" color="cobalt" className="absolute inset-0 animate-turn [animation-delay:-3s]" />
      </span>
    </div>
  );
}

function Welcome({ lang, onPick }: { lang: Language; onPick: (text: string) => void }) {
  return (
    <div className="mx-auto mt-4 flex max-w-xl flex-col items-center text-center sm:mt-10">
      <WelcomeFigure />
      <h2 className="mt-7 overflow-hidden pb-1 text-4xl font-bold tracking-tight text-balance text-ink sm:text-5xl">
        <span className="block animate-reveal [animation-delay:120ms]">{t(lang, "emptyTitle")}</span>
      </h2>
      <p className="mt-3 max-w-md animate-rise text-[15px] leading-relaxed text-ink-3 [animation-delay:260ms]">{t(lang, "emptyBody")}</p>
      <div className="mt-7 flex flex-wrap justify-center gap-2">
        {SUGGESTIONS[lang].map((suggestion, i) => {
          const bullet = BULLETS[i % BULLETS.length];
          return (
            <button
              key={suggestion}
              type="button"
              onClick={() => onPick(suggestion)}
              className="group inline-flex animate-rise items-center gap-2.5 rounded-full bg-surface py-2 pr-4 pl-3 text-sm font-medium text-ink ring-[1.5px] ring-line ring-inset transition duration-200 ease-out-soft hover:-translate-y-0.5 hover:ring-ink"
              style={{ animationDelay: `${320 + i * 70}ms` }}
            >
              <Shape kind={bullet.kind} color={bullet.color} size={12} className="transition-transform duration-300 ease-spring group-hover:rotate-90" />
              {suggestion}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Thinking({ lang, active, seen }: { lang: Language; active: Layer | null; seen: Layer[] }) {
  return (
    <li className="flex animate-rise gap-3">
      <SofiaAvatar size={30} thinking className="mt-0.5" />
      <div className="rounded-3xl rounded-tl-md bg-surface px-4 py-3 ring-1 ring-line ring-inset">
        <LayerTrack active={active} seen={seen} size={22} />
        <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-3">
          {t(lang, "thinking")}
          <span className="flex gap-0.5" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span key={i} className="size-1 animate-typing rounded-full bg-ink" style={{ animationDelay: `${i * 150}ms` }} />
            ))}
          </span>
          {active && <span className="font-semibold text-ink">· {LAYER_DOING[lang][active]}</span>}
        </p>
      </div>
    </li>
  );
}

export function ChatThread({
  items,
  lang,
  busy,
  activeLayer,
  seenLayers,
  onReply,
}: {
  items: ChatItem[];
  lang: Language;
  busy: boolean;
  activeLayer: Layer | null;
  seenLayers: Layer[];
  onReply: (text: string) => void;
}) {
  const bottom = useRef<HTMLDivElement>(null);
  const lastAgentId = items.findLast((item) => item.role === "agent")?.id;

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items.length, busy, activeLayer]);

  return (
    <div className="scrollbar-thin flex-1 overflow-y-auto px-4 py-6 sm:px-6">
      {items.length === 0 && !busy && <Welcome lang={lang} onPick={onReply} />}
      <ol aria-live="polite" className="mx-auto flex max-w-2xl flex-col gap-5">
        {items.map((item) => {
          if (item.role === "customer") {
            return (
              <li key={item.id} className="flex justify-end">
                <CustomerBubble>{item.text}</CustomerBubble>
              </li>
            );
          }
          if (item.role === "error") {
            return (
              <li key={item.id} className="flex animate-rise items-center gap-2 self-start rounded-2xl bg-danger px-4 py-2.5 text-sm font-medium text-white">
                <Icon name="alert-circle" size={16} /> {item.text}
              </li>
            );
          }
          const message = item.message;
          const interactive = item.id === lastAgentId && !busy;
          return (
            <li key={item.id} className="flex animate-rise gap-3">
              <SofiaAvatar size={30} className="mt-0.5" />
              <div className="flex min-w-0 flex-1 flex-col gap-2.5 sm:max-w-[88%]">
                <AgentBubble>{visibleText(item)}</AgentBubble>
                {message && message.candidates.length > 0 && (
                  <div className="space-y-2">
                    <Eyebrow>{t(lang, "chooseOption")}</Eyebrow>
                    <div className="grid gap-2">
                      {message.candidates.map((card, i) => (
                        <CandidateOption
                          key={card.transaction_id}
                          card={card}
                          lang={lang}
                          index={i}
                          disabled={!interactive}
                          onSelect={() => onReply(`${t(lang, "option")} ${card.option}`)}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {message?.case ? (
                  <CaseReceipt card={message.case} subject={message.subject} lang={lang} />
                ) : (
                  message?.subject && <TransactionTicket card={message.subject} lang={lang} muted={!interactive} />
                )}
                {message && message.quick_replies.length > 0 && interactive && <QuickReplies replies={message.quick_replies} onReply={onReply} />}
                {item.handoff && <HandoffNotice handoff={item.handoff} lang={lang} />}
              </div>
            </li>
          );
        })}
        {busy && <Thinking lang={lang} active={activeLayer} seen={seenLayers} />}
      </ol>
      <div ref={bottom} className="h-2" />
    </div>
  );
}
