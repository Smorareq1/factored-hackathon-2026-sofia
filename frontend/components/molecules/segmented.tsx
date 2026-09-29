"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { t } from "@/lib/i18n";
import type { Language } from "@/lib/types";

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  title?: string;
}

/** Control segmentado con indicador que se desliza (resorte) hasta la opción elegida. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className,
}: {
  value: T;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn("relative inline-grid rounded-full bg-surface-3 p-[3px]", className)}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      <span
        aria-hidden
        className="absolute top-[3px] bottom-[3px] left-[3px] rounded-full bg-ink transition-transform duration-300 ease-spring"
        style={{ width: `calc((100% - 6px) / ${options.length})`, transform: `translateX(${index * 100}%)` }}
      />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          title={option.title}
          onClick={() => onChange(option.value)}
          className={cn(
            "relative z-10 inline-flex h-8 items-center justify-center gap-1.5 px-3.5 text-xs font-semibold transition-colors duration-200",
            option.value === value ? "text-on-ink" : "text-ink-2 hover:text-ink",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function LanguageToggle({ lang, onChange }: { lang: Language; onChange: (lang: Language) => void }) {
  return (
    <Segmented
      value={lang}
      onChange={onChange}
      label={t(lang, "languageLabel")}
      options={[
        { value: "es", label: "ES", title: "Español" },
        { value: "pt", label: "PT", title: "Português" },
      ]}
    />
  );
}
