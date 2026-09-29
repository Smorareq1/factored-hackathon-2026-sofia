import { Icon } from "@/components/atoms/icon";
import { t } from "@/lib/i18n";
import type { Language } from "@/lib/types";

/** Notificación de SMS simulado que baja como en el teléfono; al tocarla, escribe el código. */
export function SmsToast({ code, lang, onUse }: { code: string; lang: Language; onUse: () => void }) {
  return (
    <button
      type="button"
      onClick={onUse}
      className="group block w-full animate-slide-down rounded-2xl bg-surface-2 p-3.5 text-left ring-1 ring-line transition duration-200 ease-out-soft ring-inset hover:-translate-y-0.5 hover:ring-ink-3"
    >
      <span className="flex items-center gap-2 text-[11px] text-ink-3">
        <span className="grid size-5 place-items-center rounded-md bg-ok text-white">
          <Icon name="message" size={12} strokeWidth={2.2} />
        </span>
        <span className="font-semibold tracking-wide text-ink-2 uppercase">{t(lang, "smsApp")}</span>
        <span className="ml-auto">{t(lang, "smsNow")}</span>
      </span>
      <span className="mt-2 block text-sm leading-snug text-ink">
        {t(lang, "smsBody")} <span className="font-mono font-semibold tracking-[0.18em]">{code}</span>. {t(lang, "smsTail")}
      </span>
      <span className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-brand-ink">
        {t(lang, "smsUse")}
        <Icon name="arrow-right" size={14} className="transition-transform duration-200 group-hover:translate-x-0.5" />
      </span>
    </button>
  );
}
