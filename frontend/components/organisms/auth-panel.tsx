"use client";

import type { FormEvent } from "react";

import { Button } from "@/components/atoms/button";
import { Icon } from "@/components/atoms/icon";
import { Card, Input } from "@/components/atoms/primitives";
import { FigureCluster } from "@/components/molecules/figures";
import { OtpInput } from "@/components/molecules/otp-input";
import { SmsToast } from "@/components/molecules/sms-toast";
import { Stepper } from "@/components/molecules/stepper";
import { t } from "@/lib/i18n";
import type { Language, SessionChallenge } from "@/lib/types";

/** Ingreso en dos pasos (REQ-11): documento → código por SMS simulado. Bloque negro, como la puerta del banco. */
export function AuthPanel({
  lang,
  document,
  onDocument,
  challenge,
  otp,
  onOtp,
  busy,
  error,
  errorKey,
  onRequest,
  onVerify,
  onBack,
  onUseSms,
}: {
  lang: Language;
  document: string;
  onDocument: (value: string) => void;
  challenge: SessionChallenge | null;
  otp: string;
  onOtp: (value: string) => void;
  busy: boolean;
  error: string | null;
  errorKey: number;
  onRequest: (event: FormEvent) => void;
  onVerify: (event: FormEvent) => void;
  onBack: () => void;
  onUseSms: () => void;
}) {
  const step = challenge ? "otp" : "document";
  return (
    <Card variant="night" className="relative animate-rise overflow-hidden rounded-[32px] p-6 [animation-delay:120ms] sm:p-8">
      <FigureCluster size={64} className="absolute top-0 right-0 overflow-hidden rounded-bl-[28px]" />
      <Stepper
        className="pr-20"
        steps={[
          { label: t(lang, "stepDocument"), state: step === "document" ? "current" : "done" },
          { label: t(lang, "stepCode"), state: step === "otp" ? "current" : "upcoming" },
          { label: t(lang, "stepChat"), state: "upcoming" },
        ]}
      />

      {step === "document" ? (
        <form key="document" onSubmit={onRequest} className="mt-8 animate-fade space-y-5">
          <div>
            <h2 className="text-3xl font-bold tracking-tight text-ink">{t(lang, "loginTitle")}</h2>
            <p className="mt-1 text-sm text-ink-3">{t(lang, "loginHint")}</p>
          </div>
          <label className="block space-y-1.5">
            <span className="text-sm font-semibold text-ink-2">{t(lang, "documentLabel")}</span>
            <Input
              icon="id-card"
              value={document}
              onChange={(e) => onDocument(e.target.value)}
              placeholder="MX-DEMO-001"
              autoComplete="off"
              spellCheck={false}
              required
              className="font-mono"
            />
          </label>
          <p className="flex items-start gap-2.5 rounded-2xl bg-surface-2 px-3.5 py-3 text-xs leading-relaxed text-ink-2">
            <Icon name="lock" size={15} className="mt-px shrink-0 text-accent" />
            {t(lang, "documentHint")}
          </p>
          <Button type="submit" size="lg" block loading={busy} disabled={!document.trim()} iconRight="arrow-right">
            {t(lang, "continue")}
          </Button>
        </form>
      ) : (
        <form key="otp" onSubmit={onVerify} className="mt-8 animate-fade space-y-5">
          <div>
            <h2 className="text-3xl font-bold tracking-tight text-ink">{t(lang, "otpTitle")}</h2>
            <p className="mt-1 text-sm text-ink-3">{t(lang, "otpNotice")}</p>
          </div>
          {challenge?.simulated_otp && <SmsToast code={challenge.simulated_otp} lang={lang} onUse={onUseSms} />}
          <OtpInput value={otp} onChange={onOtp} label={t(lang, "otpLabel")} invalid={Boolean(error)} errorKey={errorKey} autoFocus />
          <div className="flex gap-2">
            <Button variant="secondary" size="lg" icon="chevron-left" onClick={onBack}>
              {t(lang, "back")}
            </Button>
            <Button type="submit" size="lg" className="flex-1" loading={busy} disabled={otp.length < 6} icon="shield-check">
              {t(lang, "verify")}
            </Button>
          </div>
        </form>
      )}

      {error && (
        <p role="alert" className="mt-4 flex animate-rise items-center gap-2 text-sm text-danger-ink">
          <Icon name="alert-circle" size={16} />
          {error}
        </p>
      )}
    </Card>
  );
}
