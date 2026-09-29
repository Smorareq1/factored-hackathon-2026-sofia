"use client";

import { type FormEvent, useState } from "react";

import { Icon } from "@/components/atoms/icon";
import { cn } from "@/lib/cn";
import { t } from "@/lib/i18n";
import type { Language } from "@/lib/types";

const MAX = 2000; // purpose.limits.max_message_chars

export function Composer({ lang, disabled, onSend }: { lang: Language; disabled: boolean; onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const ready = !disabled && text.trim().length > 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText("");
  }

  return (
    <form onSubmit={submit} className="border-t border-line bg-surface px-4 pt-3 pb-4 sm:px-6">
      <div className="mx-auto max-w-2xl">
        <div className="flex items-center gap-2 rounded-full border-[1.5px] border-line-strong bg-surface p-1.5 pl-5 transition duration-200 focus-within:border-ink">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t(lang, "composerPlaceholder")}
            maxLength={MAX}
            aria-label={t(lang, "composerPlaceholder")}
            className="h-10 min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-ink-4 focus-visible:outline-none"
          />
          {text.length > MAX * 0.75 && (
            <span className="font-mono text-[11px] text-ink-3 tabular-nums">
              {text.length}/{MAX}
            </span>
          )}
          <button
            type="submit"
            disabled={!ready}
            aria-label={t(lang, "send")}
            className={cn(
              "grid size-10 shrink-0 place-items-center rounded-full transition duration-200 ease-out-soft active:scale-90",
              ready ? "bg-brand text-white hover:bg-brand-strong" : "bg-surface-3 text-ink-4",
            )}
          >
            <Icon name="send" size={18} className={cn("transition-transform duration-300 ease-spring", ready && "translate-x-px -translate-y-px")} />
          </button>
        </div>
        <p className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-ink-3">
          <Icon name="shield-check" size={13} className="text-brand-ink" />
          {t(lang, "composerTrust")}
        </p>
      </div>
    </form>
  );
}
