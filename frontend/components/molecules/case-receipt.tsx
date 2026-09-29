import { MerchantMonogram } from "@/components/atoms/avatar";
import { Badge } from "@/components/atoms/badge";
import { Icon } from "@/components/atoms/icon";
import { Mono } from "@/components/atoms/primitives";
import type { Tone } from "@/components/atoms/tone";
import { t } from "@/lib/i18n";
import type { CaseCard, Language, TransactionCard } from "@/lib/types";

import { type Step, Stepper } from "./stepper";

const STATUS_TONE: Record<string, Tone> = { open: "brand", in_review: "info", resolved: "ok", rejected: "danger" };

function steps(card: CaseCard, lang: Language): Step[] {
  const finished = card.status === "resolved" || card.status === "rejected";
  return [
    { label: t(lang, "caseRegistered"), state: "done" },
    { label: t(lang, "caseVerified"), state: card.verified ? "done" : "current" },
    { label: t(lang, "caseReview"), state: finished ? "done" : card.verified ? "current" : "upcoming" },
    {
      label: t(lang, card.status === "rejected" ? "caseRejected" : "caseResolved"),
      state: card.status === "rejected" ? "error" : card.status === "resolved" ? "done" : "upcoming",
    },
  ];
}

/** Comprobante del caso (REQ-09): solo aparece si la disputa se releyó en el banco después de crearla. */
export function CaseReceipt({ card, subject, lang }: { card: CaseCard; subject: TransactionCard | null; lang: Language }) {
  return (
    <div className="animate-pop overflow-hidden rounded-3xl bg-surface ring-1 ring-line ring-inset">
      <div className="relative flex items-center gap-3 overflow-hidden bg-brand px-4 py-4 text-white">
        <span aria-hidden className="absolute -top-6 -right-6 size-20 rounded-full bg-fig-sun" />
        <span className="grid size-10 place-items-center rounded-2xl bg-white text-brand">
          <Icon name="receipt" size={20} strokeWidth={2} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold tracking-[0.1em] uppercase opacity-85">{t(lang, "caseTitle")}</p>
          <p className="truncate font-mono text-lg font-bold">{card.dispute_id}</p>
        </div>
        <Badge tone={STATUS_TONE[card.status] ?? "neutral"} variant="solid" size="md" icon={card.verified ? "shield-check" : "circle-dashed"} className="relative ring-2 ring-white">
          {card.status_display}
        </Badge>
      </div>
      {subject && (
        <div className="flex items-center gap-3 border-t border-line px-4 py-2.5 text-sm">
          <MerchantMonogram name={subject.merchant} size={28} />
          <span className="min-w-0 flex-1 truncate text-ink-2">
            {subject.merchant} · {subject.date}
          </span>
          <span className="font-mono font-semibold text-ink tabular-nums">{subject.amount_display}</span>
        </div>
      )}
      <div className="border-t border-line px-4 pt-4 pb-3">
        <Stepper steps={steps(card, lang)} labels="below" />
      </div>
      {card.verified && (
        <p className="flex items-center gap-2 border-t border-line bg-surface-2 px-4 py-2.5 text-[11px] text-ink-3">
          <Icon name="shield-check" size={14} className="text-ok" />
          {t(lang, "caseProof")}
          <Mono className="ml-auto text-ink-2">GET /disputes/{card.dispute_id}</Mono>
        </p>
      )}
    </div>
  );
}
