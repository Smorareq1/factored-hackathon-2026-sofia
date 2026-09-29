"use client";

import { useRef, useState } from "react";

import { cn } from "@/lib/cn";

/**
 * Código de 6 dígitos en casillas. Un solo <input> real (transparente, encima) recibe el teclado, el pegado y
 * el autocompletado `one-time-code`; las casillas solo dibujan. `errorKey` cambia → la fila tiembla.
 */
export function OtpInput({
  value,
  onChange,
  label,
  length = 6,
  invalid = false,
  errorKey = 0,
  autoFocus = false,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  length?: number;
  invalid?: boolean;
  errorKey?: number;
  autoFocus?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(autoFocus);
  const caret = Math.min(value.length, length - 1);

  return (
    <div className="relative">
      <input
        ref={input}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, length))}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={length}
        aria-label={label}
        aria-invalid={invalid || undefined}
        autoFocus={autoFocus}
        className="absolute inset-0 z-10 h-full w-full cursor-text opacity-0"
      />
      <div key={errorKey} className={cn("grid gap-2", errorKey > 0 && "animate-shake")} style={{ gridTemplateColumns: `repeat(${length}, minmax(0, 1fr))` }} aria-hidden>
        {Array.from({ length }, (_, i) => {
          const digit = value[i];
          const active = focused && i === caret && value.length < length;
          return (
            <div
              key={i}
              className={cn(
                "grid h-14 place-items-center rounded-2xl border-[1.5px] bg-surface font-mono text-2xl font-bold text-ink transition duration-200",
                invalid ? "border-danger bg-danger-soft" : active ? "border-brand ring-[3px] ring-brand" : digit ? "border-ink bg-surface" : "border-line-strong",
              )}
            >
              {digit ? (
                <span key={digit + i} className="animate-pop">
                  {digit}
                </span>
              ) : (
                active && <span className="h-6 w-0.5 animate-blink rounded-full bg-brand" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
