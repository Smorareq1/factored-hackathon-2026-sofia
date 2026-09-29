"use client";

// Login de la demo con OTP simulado (REQ-11): el número de documento solo no basta.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/atoms/icon";
import { type FigureColor, Shape, type ShapeKind } from "@/components/atoms/shape";
import { Brand } from "@/components/molecules/brand";
import { CustomerTile } from "@/components/molecules/customer-tile";
import { FigureFrieze } from "@/components/molecules/figures";
import { LanguageToggle } from "@/components/molecules/segmented";
import { AuthPanel } from "@/components/organisms/auth-panel";
import { AuthShell } from "@/components/templates/shells";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { t, type UiKey } from "@/lib/i18n";
import { newThreadId, saveSession } from "@/lib/session";
import type { DemoCustomer, Language, SessionChallenge } from "@/lib/types";

const PROMISES: { kind: ShapeKind; color: FigureColor; key: UiKey }[] = [
  { kind: "circle", color: "cobalt", key: "promiseVerified" },
  { kind: "square", color: "coral", key: "promiseConfirm" },
  { kind: "triangle", color: "ink", key: "promiseHuman" },
];

export default function LoginScreen() {
  const router = useRouter();
  const [lang, setLang] = useState<Language>("es");
  const [customers, setCustomers] = useState<DemoCustomer[]>([]);
  const [document, setDocument] = useState("");
  const [challenge, setChallenge] = useState<SessionChallenge | null>(null);
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const typing = useRef<number | null>(null);

  useEffect(() => {
    api.demoCustomers().then(setCustomers, () => setCustomers([]));
    return () => {
      if (typing.current) window.clearInterval(typing.current);
    };
  }, []);

  const selected = customers.find((c) => c.document_number === document.trim());

  function pick(customer: DemoCustomer) {
    setDocument(customer.document_number);
    setChallenge(null);
    setError(null);
    // João habla portugués: la UI lo acompaña (Sofía igual detecta el idioma en cada turno).
    if (customer.role === "customer") setLang(/portugu/i.test(customer.label) ? "pt" : "es");
  }

  async function requestCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setChallenge(await api.startSession(document.trim()));
      setOtp("");
    } catch {
      setError(t(lang, "errorGeneric"));
    } finally {
      setBusy(false);
    }
  }

  /** Tocar el SMS escribe el código dígito por dígito (se ve cómo se llena). */
  function fillFromSms() {
    const code = challenge?.simulated_otp;
    if (!code) return;
    if (typing.current) window.clearInterval(typing.current);
    setError(null);
    let i = 0;
    typing.current = window.setInterval(() => {
      i += 1;
      setOtp(code.slice(0, i));
      if (i >= code.length && typing.current) window.clearInterval(typing.current);
    }, 70);
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.verifySession(challenge.challenge_id, otp.trim());
      saveSession({
        token: session.access_token,
        role: session.role,
        expiresAt: session.expires_at,
        label: selected?.label ?? document,
        country: selected?.country ?? null,
        language: lang,
        threadId: newThreadId(),
      });
      router.push(session.role === "agent" ? "/console" : "/chat");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t(lang, "otpInvalid") : t(lang, "errorGeneric"));
      setErrorKey((k) => k + 1);
      setBusy(false);
    }
  }

  return (
    <AuthShell
      top={
        <>
          <Brand lang={lang} animate />
          <div className="flex items-center gap-2">
            <Link
              href="/design"
              className="hidden h-9 items-center gap-1.5 rounded-full px-3.5 text-xs font-semibold text-ink-2 transition hover:bg-surface-3 hover:text-ink sm:inline-flex"
            >
              <Icon name="palette" size={15} />
              {t(lang, "designSystem")}
            </Link>
            <LanguageToggle lang={lang} onChange={setLang} />
          </div>
        </>
      }
      bottom={<FigureFrieze />}
    >
      <div className="grid items-start gap-10 lg:grid-cols-[1.12fr_1fr] lg:gap-16">
        <section>
          <p className="flex animate-rise items-center gap-2.5 text-xs font-semibold tracking-[0.1em] text-ink-2 uppercase">
            <span aria-hidden className="flex items-center gap-1">
              <Shape kind="circle" color="cobalt" size={10} />
              <Shape kind="square" color="coral" size={10} />
              <Shape kind="triangle" color="ink" size={10} />
            </span>
            {t(lang, "heroEyebrow")}
          </p>
          <h1
            className={cn(
              "headline mt-5 text-ink",
              lang === "pt" ? "text-[clamp(2.75rem,6vw,5.25rem)]" : "text-[clamp(3rem,7vw,6.25rem)]",
            )}
          >
            <span className="-mb-[0.12em] block overflow-hidden pb-[0.12em]">
              <span className="block animate-reveal">{t(lang, "heroTitle")}</span>
            </span>
            <span className="-mb-[0.12em] block overflow-hidden pb-[0.12em]">
              <span className="block animate-reveal text-brand [animation-delay:110ms]">Sofía.</span>
            </span>
          </h1>
          <p className="mt-6 max-w-md animate-rise text-lg leading-relaxed text-ink-2 [animation-delay:240ms]">{t(lang, "heroBody")}</p>
          <ul className="mt-9 grid gap-x-5 gap-y-4 sm:grid-cols-3">
            {PROMISES.map((promise, i) => (
              <li
                key={promise.key}
                className="animate-rise border-t-2 border-ink pt-3 text-sm leading-snug font-medium text-ink"
                style={{ animationDelay: `${320 + i * 70}ms` }}
              >
                <Shape kind={promise.kind} color={promise.color} size={16} className="mb-2 block" />
                {t(lang, promise.key)}
              </li>
            ))}
          </ul>
        </section>

        <AuthPanel
          lang={lang}
          document={document}
          onDocument={setDocument}
          challenge={challenge}
          otp={otp}
          onOtp={(value) => {
            setOtp(value);
            setError(null);
          }}
          busy={busy}
          error={error}
          errorKey={errorKey}
          onRequest={requestCode}
          onVerify={verify}
          onBack={() => {
            setChallenge(null);
            setError(null);
          }}
          onUseSms={fillFromSms}
        />
      </div>

      <section className="mt-14 lg:mt-16">
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-1 border-b-2 border-ink pb-3">
          <h2 className="text-2xl font-bold tracking-tight text-ink">{t(lang, "demoCustomers")}</h2>
          <span className="text-xs text-ink-3">{t(lang, "demoCustomersHint")}</span>
        </div>
        <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {customers.map((customer, i) => (
            <li key={customer.document_number}>
              <CustomerTile customer={customer} index={i} selected={document.trim() === customer.document_number} onSelect={() => pick(customer)} />
            </li>
          ))}
        </ul>
      </section>
    </AuthShell>
  );
}
