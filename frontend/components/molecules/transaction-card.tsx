import type { CSSProperties } from "react";

import { MerchantMonogram } from "@/components/atoms/avatar";
import { Icon } from "@/components/atoms/icon";
import { Eyebrow, Mono } from "@/components/atoms/primitives";
import { cn } from "@/lib/cn";
import { t } from "@/lib/i18n";
import type { CandidateCard, Language, TransactionCard } from "@/lib/types";

/** Transacción candidata: se elige con un toque y manda el texto equivalente ("Opción 2"). */
export function CandidateOption({
  card,
  lang,
  disabled,
  onSelect,
  index = 0,
}: {
  card: CandidateCard;
  lang: Language;
  disabled: boolean;
  onSelect: () => void;
  index?: number;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        "group flex w-full animate-rise items-center gap-3 rounded-3xl bg-surface p-3 text-left ring-1 ring-line ring-inset",
        "transition duration-200 ease-out-soft enabled:hover:-translate-y-0.5 enabled:hover:ring-[1.5px] enabled:hover:ring-ink",
        "disabled:opacity-60",
      )}
      style={{ animationDelay: `${140 + index * 70}ms` }}
    >
      <MerchantMonogram name={card.merchant} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-ink">{card.merchant}</span>
        <span className="mt-0.5 flex items-center gap-1 text-xs text-ink-3">
          <Icon name="calendar" size={12} />
          {card.date}
        </span>
      </span>
      <span className="flex flex-col items-end gap-1">
        <span className="font-mono text-sm font-semibold text-ink tabular-nums">{card.amount_display}</span>
        <span className="inline-flex h-5 items-center rounded-full bg-surface-3 px-2 text-[10px] font-bold text-ink-2 transition-colors group-hover:bg-brand group-hover:text-white group-disabled:bg-surface-3 group-disabled:text-ink-2">
          {t(lang, "option")} {card.option}
        </span>
      </span>
    </button>
  );
}

/** La transacción de la que habla el mensaje, como ticket con muescas (antes de confirmar). */
export function TransactionTicket({ card, lang, muted = false }: { card: TransactionCard; lang: Language; muted?: boolean }) {
  return (
    <div className={cn("animate-rise drop-shadow-[0_0_1px_var(--line-strong)]", muted && "opacity-80")}>
      <div className="ticket rounded-3xl bg-surface" style={{ "--notch-y": "68px" } as CSSProperties}>
        <div className="flex h-[68px] items-center gap-3 px-4">
          <MerchantMonogram name={card.merchant} size={40} />
          <div className="min-w-0 flex-1">
            <Eyebrow>{t(lang, "transaction")}</Eyebrow>
            <p className="truncate font-bold text-ink">{card.merchant}</p>
          </div>
          <p className="font-mono text-lg font-bold text-ink tabular-nums">{card.amount_display}</p>
        </div>
        <div className="mx-4 border-t-2 border-dashed border-line" />
        <div className="flex items-center justify-between gap-3 px-4 pt-2.5 pb-3 text-xs text-ink-3">
          <span className="flex items-center gap-1.5">
            <Icon name="calendar" size={14} />
            {card.date}
          </span>
          <Mono>{card.transaction_id}</Mono>
        </div>
      </div>
    </div>
  );
}
