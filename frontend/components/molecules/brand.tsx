import { SofiaMark } from "@/components/atoms/logo";
import { t } from "@/lib/i18n";
import type { Language } from "@/lib/types";

/** Logotipo completo: marca + nombre + bajada. */
export function Brand({ lang, compact = false, animate = false }: { lang: Language; compact?: boolean; animate?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <SofiaMark size={compact ? 32 : 36} animate={animate} />
      <div className="leading-tight">
        <p className="text-[17px] font-bold tracking-tight text-ink">Sofía</p>
        {!compact && <p className="text-xs text-ink-3">{t(lang, "tagline")}</p>}
      </div>
    </div>
  );
}
