"use client";

// Sofía DS en vivo: tokens, iconos y cada nivel del diseño atómico con datos de ejemplo (sintéticos).
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { Avatar, MerchantMonogram, SofiaAvatar } from "@/components/atoms/avatar";
import { Badge } from "@/components/atoms/badge";
import { Button, IconButton } from "@/components/atoms/button";
import { Flag } from "@/components/atoms/flag";
import { Icon } from "@/components/atoms/icon";
import { ICON_NAMES } from "@/components/atoms/icon-set";
import { Meter } from "@/components/atoms/meter";
import { Card, Eyebrow, Input, Mono, Skeleton } from "@/components/atoms/primitives";
import { FIGURE_BG, type FigureColor, Shape, type ShapeKind } from "@/components/atoms/shape";
import { Spinner } from "@/components/atoms/spinner";
import { StatusDot } from "@/components/atoms/status-dot";
import type { Tone } from "@/components/atoms/tone";
import { Brand } from "@/components/molecules/brand";
import { CaseReceipt } from "@/components/molecules/case-receipt";
import { BarList } from "@/components/molecules/charts/bar-list";
import { ColumnChart } from "@/components/molecules/charts/column-chart";
import { RingGauge } from "@/components/molecules/charts/ring-gauge";
import { Sparkline } from "@/components/molecules/charts/sparkline";
import { SplitBar } from "@/components/molecules/charts/split-bar";
import { HandoffNotice, LayerTrack, QuickReplies, RouteBadge } from "@/components/molecules/chat-bits";
import { CustomerTile } from "@/components/molecules/customer-tile";
import { CustomerFigure, FigureCluster, FigureFrieze } from "@/components/molecules/figures";
import { ActionRow, FactRow, JsonView, PolicyLadder } from "@/components/molecules/evidence";
import { OtpInput } from "@/components/molecules/otp-input";
import { LanguageToggle, Segmented } from "@/components/molecules/segmented";
import { SmsToast } from "@/components/molecules/sms-toast";
import { StatTile } from "@/components/molecules/stat-tile";
import { Stepper } from "@/components/molecules/stepper";
import { CandidateOption, TransactionTicket } from "@/components/molecules/transaction-card";
import { HandoffSheet } from "@/components/organisms/handoff-sheet";
import { TurnWaterfall } from "@/components/organisms/turn-waterfall";
import { cn } from "@/lib/cn";
import { useNow } from "@/lib/hooks";
import { LAYERS } from "@/lib/layers";
import type { Handoff, HandoffFeedback, HandoffFeedbackRecord, Language, Layer, LayerEvent, Route } from "@/lib/types";

// ───────────── datos de ejemplo (sintéticos, iguales a los clientes demo) ─────────────
const T0 = Date.parse("2026-09-28T15:00:00.000Z");
const ev = (node: string, layer: Layer, code: string, at: number, since: number, params: LayerEvent["params"] = {}): LayerEvent => ({
  turn: 3,
  layer,
  node,
  status: "ok",
  code,
  params,
  started_at: new Date(T0 + at).toISOString(),
  duration_ms: since,
  span_id: null,
});

const SAMPLE_EVENTS: LayerEvent[] = [
  ev("sense", "SENSE", "session_valid", 16, 16),
  ev("sense", "SENSE", "tool_call", 18, 18, { method: "GET", path: "/session/me", http_status: 200, attempt: 1, ms: 12 }),
  ev("interpret", "INTERPRET", "intent_classified", 42, 20, { intent: "dispute_new", confidence: 0.91 }),
  ev("interpret", "INTERPRET", "tool_call", 104, 82, { method: "GET", path: "/transactions", http_status: 200, attempt: 1, ms: 44 }),
  ev("decide", "DECIDE", "rule_applied", 150, 44, { rule_id: "POL-5", route: "auto" }),
  ev("decide", "DECIDE", "tool_call", 152, 46, { method: "POST", path: "/disputes/eligibility", http_status: 200, attempt: 1, ms: 39 }),
  ev("respond", "GOVERN", "grounding_passed", 164, 8),
  ev("respond", "ORCHESTRATE", "response_ready", 171, 15, { source: "template", llm_calls: 0 }),
];

const SAMPLE_HANDOFF: Handoff = {
  handoff_id: "HO-2026-000123",
  created_at: new Date(T0).toISOString(),
  schema_version: "1.0",
  language: "es",
  customer_id: "C90000001",
  authenticated: true,
  request_summary: "Cliente no reconoce un cargo de 18999.00 MXN en Liverpool del 2026-09-20. Motivo: revisión humana por política (POL-6).",
  customer_claim: "not_recognized",
  verified_facts: [
    { fact: "La transacción TX-MX-0004 existe y pertenece al cliente", source: "GET /transactions/TX-MX-0004" },
    { fact: "Monto 18999.00 MXN (≈ 1050.00 USD)", source: "GET /transactions/TX-MX-0004" },
    { fact: "Política POL-6: monto alto (ruta human)", source: "POST /disputes/eligibility" },
  ],
  actions_taken: [
    { action: "eligibility_check", result: "route=human rule=POL-6", verified: true },
    { action: "create_handoff", result: "HO-2026-000123", verified: true },
  ],
  open_questions: ["¿El cliente reconoce otras transacciones recientes del mismo comercio?"],
  risk_flags: ["high_amount"],
  reason_for_handoff: "POL-6",
  system_version: "proposed",
  trace_id: null,
};

const LEVELS: { name: string; kind: ShapeKind; bg: FigureColor; fg: FigureColor; items: string }[] = [
  { name: "Átomos", kind: "circle", bg: "cobalt", fg: "sun", items: "Icon · Shape · Button · Badge · StatusDot · Meter · Avatar · Flag · Logo · Input · Card · Spinner" },
  { name: "Moléculas", kind: "half", bg: "sun", fg: "ink", items: "Figuras · OtpInput · Stepper · SmsToast · CaseReceipt · LayerTrack · PolicyLadder · gráficas" },
  { name: "Organismos", kind: "quarter", bg: "coral", fg: "paper", items: "ChatThread · Composer · GlassBox · TurnWaterfall · HandoffSheet · FeedbackForm · QueueOverview" },
  { name: "Plantillas", kind: "arch", bg: "mist", fg: "cobalt", items: "AuthShell · WorkspaceShell · AppHeader" },
  { name: "Pantallas", kind: "square", bg: "ink", fg: "coral", items: "Login · Chat · Consola · Sistema de diseño" },
];

const SHAPES: ShapeKind[] = ["circle", "half", "quarter", "arch", "square", "diamond", "triangle", "leaf", "ring", "dot"];
const SHAPE_COLORS: FigureColor[] = ["cobalt", "sun", "coral", "ink"];

const TOKENS: { group: string; names: string[] }[] = [
  { group: "Superficies", names: ["bg", "surface", "surface-2", "surface-3", "line", "line-strong"] },
  { group: "Tinta", names: ["ink", "ink-2", "ink-3", "ink-4"] },
  { group: "Marca (cobalto = Sofía · sol = persona)", names: ["brand", "brand-strong", "brand-soft", "brand-ink", "accent", "accent-strong", "accent-soft", "on-ink"] },
  { group: "Figuras (solo decorativas)", names: ["fig-cobalt", "fig-sun", "fig-coral", "fig-ink", "fig-paper", "fig-mist"] },
  { group: "Estado", names: ["ok", "ok-soft", "warn", "warn-soft", "danger", "danger-soft", "info", "info-soft"] },
  { group: "Gráficas (validadas CVD)", names: ["series-1", "series-2", "grid"] },
];

const TONES: Tone[] = ["neutral", "brand", "accent", "ok", "warn", "danger", "info"];
const ROUTES: Route[] = ["auto", "clarify", "abstain", "escalate", "deny", "reauth"];

// ───────────── piezas de la página ─────────────
function Section({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 space-y-6">
      <div>
        <Eyebrow>{eyebrow}</Eyebrow>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-ink">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Specimen({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("flex flex-col gap-4 p-5", className)}>
      <p className="font-mono text-[11px] text-ink-3">{label}</p>
      <div className="flex flex-1 flex-wrap items-center gap-3">{children}</div>
    </Card>
  );
}

/** Pista de capas en loop, como se ve mientras Sofía piensa. */
function LayerTrackDemo() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setStep((s) => (s + 1) % 7), 900);
    return () => window.clearInterval(id);
  }, []);
  const layers = LAYERS.filter((l) => l !== "LEARN");
  return <LayerTrack active={layers[step] ?? null} seen={layers.slice(0, step + 1)} />;
}

function OtpDemo() {
  const [code, setCode] = useState("");
  return (
    <div className="w-full max-w-sm space-y-3">
      <OtpInput value={code} onChange={setCode} label="Código de ejemplo" />
      <Button size="sm" variant="soft" icon="message" onClick={() => setCode("482913")}>
        Autocompletar
      </Button>
    </div>
  );
}

export default function DesignScreen() {
  const [theme, setTheme] = useState<"light" | "night">("light");
  const [lang, setLang] = useState<Language>("es");
  const [segment, setSegment] = useState<"a" | "b" | "c">("a");
  const [replay, setReplay] = useState(0);
  // En la demo el feedback no sale a ninguna API: se simula la respuesta de SIM.
  const [demoFeedback, setDemoFeedback] = useState<HandoffFeedbackRecord | null>(null);
  async function sendDemoFeedback(feedback: HandoffFeedback) {
    await new Promise((resolve) => window.setTimeout(resolve, 600));
    setDemoFeedback({ ...feedback, handoff_id: SAMPLE_HANDOFF.handoff_id, reviewer_id: "A90000001", submitted_at: new Date().toISOString() });
  }
  const now = useNow();

  return (
    <div className="min-h-dvh bg-bg">
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <Brand lang="es" compact />
            <Badge tone="accent" variant="solid" icon="palette">
              Sofía DS
            </Badge>
          </div>
          <nav className="hidden items-center gap-1 text-xs font-medium text-ink-3 lg:flex">
            {["tokens", "formas", "iconos", "atomos", "moleculas", "graficas", "organismos", "movimiento"].map((anchor) => (
              <a key={anchor} href={`#${anchor}`} className="rounded-full px-2.5 py-1.5 capitalize transition hover:bg-surface-3 hover:text-ink">
                {anchor.replace("atomos", "átomos").replace("moleculas", "moléculas").replace("graficas", "gráficas")}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Segmented
              value={theme}
              onChange={setTheme}
              label="Tema de la vista previa"
              options={[
                { value: "light", label: "Claro" },
                { value: "night", label: "Noche" },
              ]}
            />
            <Link href="/" className="hidden rounded-full px-3.5 py-2 text-xs font-semibold text-ink-2 transition hover:bg-surface-3 hover:text-ink sm:block">
              Volver
            </Link>
          </div>
        </div>
      </header>

      <div data-theme={theme === "night" ? "night" : undefined} className="bg-bg transition-colors duration-300">
        <main className="mx-auto max-w-6xl space-y-16 px-5 py-12 sm:px-8">
          {/* intro */}
          <section className="space-y-6">
            <h1 className="headline max-w-3xl text-5xl text-ink sm:text-7xl">
              <span className="-mb-[0.12em] block overflow-hidden pb-[0.12em]">
                <span className="block animate-reveal">Un sistema,</span>
              </span>
              <span className="-mb-[0.12em] block overflow-hidden pb-[0.12em]">
                <span className="block animate-reveal text-brand [animation-delay:110ms]">cinco niveles.</span>
              </span>
            </h1>
            <p className="max-w-2xl text-lg text-ink-2">
              Todo es propio: colores sólidos, figuras geométricas, iconos dibujados en una grilla de 24 px, gráficas en SVG y un solo ritmo de
              movimiento. Sin degradados, sin vidrio, sin sombras difusas: los planos se separan por color. Cada nivel se arma solo con piezas del
              nivel anterior; el tema &quot;noche&quot; de la caja de cristal reusa los mismos componentes cambiando solo los tokens.
            </p>
            <ol className="grid gap-2 sm:grid-cols-5">
              {LEVELS.map((level, i) => (
                <li key={level.name} className="relative animate-rise" style={{ animationDelay: `${i * 70}ms` }}>
                  <Card className="h-full overflow-hidden">
                    <span className={cn("relative block aspect-[2/1] overflow-hidden", FIGURE_BG[level.bg])}>
                      <span className="absolute inset-y-[14%] left-1/2 aspect-square -translate-x-1/2">
                        <Shape kind={level.kind} color={level.fg} className="animate-turn" style={{ animationDelay: `${-i * 1.2}s` }} />
                      </span>
                    </span>
                    <p className="mt-3 px-4 text-sm font-bold text-ink">
                      <span className="font-mono text-ink-3">{i + 1}.</span> {level.name}
                    </p>
                    <p className="mt-1 px-4 pb-4 text-xs leading-relaxed text-ink-3">{level.items}</p>
                  </Card>
                  {i < LEVELS.length - 1 && (
                    <Icon name="chevron-right" size={16} className="absolute top-1/2 -right-3 z-10 hidden -translate-y-1/2 text-ink-4 sm:block" />
                  )}
                </li>
              ))}
            </ol>
          </section>

          <Section id="tokens" eyebrow="Fundamentos" title="Tokens de color">
            <div className="space-y-5">
              {TOKENS.map((group) => (
                <div key={group.group}>
                  <p className="mb-2 text-xs font-semibold text-ink-2">{group.group}</p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
                    {group.names.map((name) => (
                      <div key={name} className="overflow-hidden rounded-xl border border-line bg-surface">
                        <div className="h-14 border-b border-line" style={{ background: `var(--${name})` }} />
                        <p className="px-2.5 py-2 font-mono text-[11px] text-ink-2">--{name}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <Specimen label="headline · Geist 700 · −0.045em">
                <p className="headline text-5xl text-ink">
                  Hola, soy <span className="text-brand">Sofía.</span>
                </p>
              </Specimen>
              <Specimen label="font-sans · Geist">
                <div>
                  <p className="text-2xl font-semibold tracking-tight text-ink">Ficha de transferencia</p>
                  <p className="text-sm text-ink-2">Texto de lectura a 15 px con interlineado 1.6.</p>
                </div>
              </Specimen>
              <Specimen label="font-mono · Geist Mono">
                <p className="font-mono text-sm text-ink">GET /disputes/DSP-2026-000900 → 200</p>
              </Specimen>
            </div>
          </Section>

          <Section id="formas" eyebrow="Fundamentos" title="Formas">
            <p className="-mt-3 max-w-2xl text-sm text-ink-3">
              Diez figuras sobre una grilla de 100 × 100, en cuatro colores sólidos. Son decorativas (nunca llevan significado solas) y se mueven
              por piezas: giran de a un cuarto de vuelta, suben o pasan de cuadrado a círculo. Con prefers-reduced-motion se quedan quietas.
            </p>
            <ul className="grid grid-cols-5 gap-2 sm:grid-cols-10">
              {SHAPES.map((kind, i) => (
                <li key={kind} className="group flex flex-col items-center gap-2 rounded-2xl bg-surface p-3 ring-1 ring-line ring-inset">
                  <Shape kind={kind} color={SHAPE_COLORS[i % SHAPE_COLORS.length]} size={44} className="transition-transform duration-500 ease-spring group-hover:rotate-90" />
                  <span className="font-mono text-[10px] text-ink-3">{kind}</span>
                </li>
              ))}
            </ul>
            <div className="grid gap-3 lg:grid-cols-[2fr_1fr]">
              <Specimen label="CustomerFigure · una por cliente demo (se mueve cuando está elegida)">
                <div className="grid w-full grid-cols-5 gap-2">
                  {[0, 1, 2, 3, 4].map((variant) => (
                    <CustomerFigure key={variant} variant={variant} active className="group aspect-square w-full rounded-2xl" />
                  ))}
                </div>
              </Specimen>
              <Specimen label="FigureCluster">
                <FigureCluster size={96} className="overflow-hidden rounded-3xl" />
                <FigureCluster size={56} className="overflow-hidden rounded-2xl" />
              </Specimen>
            </div>
            <Card className="overflow-hidden">
              <p className="px-5 pt-4 pb-3 font-mono text-[11px] text-ink-3">FigureFrieze · una pieza gira cada 1.3 s; al pasar el cursor, gira la que tocas</p>
              <FigureFrieze />
            </Card>
          </Section>

          <Section id="iconos" eyebrow="Iconografía" title={`${ICON_NAMES.length} iconos propios`}>
            <p className="-mt-3 max-w-2xl text-sm text-ink-3">
              Trazo de 1.75 sobre 24 px, puntas redondeadas y <Mono>currentColor</Mono>. Incluye un icono por cada una de las 7 capas y la &quot;caja de cristal&quot;: un cubo
              con sus aristas ocultas a la vista.
            </p>
            <ul className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-8">
              {ICON_NAMES.map((name, i) => (
                <li
                  key={name}
                  className="group flex animate-rise flex-col items-center gap-2 rounded-2xl bg-surface px-2 py-4 text-ink-2 ring-1 ring-line transition duration-200 ring-inset hover:bg-ink hover:text-on-ink hover:ring-ink"
                  style={{ animationDelay: `${Math.min(i, 40) * 12}ms` }}
                >
                  <Icon name={name} size={24} className="transition-transform duration-300 ease-spring group-hover:scale-125" />
                  <span className="max-w-full truncate font-mono text-[10px]">{name}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="atomos" eyebrow="Nivel 1" title="Átomos">
            <div className="grid gap-3 lg:grid-cols-2">
              <Specimen label="Button · variantes">
                <Button icon="check">Primario</Button>
                <Button variant="ink">Tinta</Button>
                <Button variant="secondary">Secundario</Button>
                <Button variant="soft">Suave</Button>
                <Button variant="ghost">Fantasma</Button>
                <Button variant="danger" icon="key">
                  Peligro
                </Button>
              </Specimen>
              <Specimen label="Button · tamaños y estados">
                <Button size="sm">Chico</Button>
                <Button size="md">Mediano</Button>
                <Button size="lg" iconRight="arrow-right">
                  Grande
                </Button>
                <Button loading>Cargando</Button>
                <Button disabled>Deshabilitado</Button>
              </Specimen>
              <Specimen label="Badge · tonos (soft · solid · outline)">
                {TONES.map((tone) => (
                  <Badge key={tone} tone={tone}>
                    {tone}
                  </Badge>
                ))}
                <Badge tone="brand" variant="solid" icon="check">
                  solid
                </Badge>
                <Badge tone="accent" variant="outline" icon="layer-decide" mono>
                  POL-6
                </Badge>
              </Specimen>
              <Specimen label="IconButton · StatusDot · Spinner">
                <IconButton icon="chat-plus" label="Nueva conversación" />
                <IconButton icon="glass-box" label="Caja de cristal" pressed />
                <IconButton icon="refresh" label="Actualizar" spinning />
                <span className="mx-2 h-6 w-px bg-line" />
                {(["ok", "warn", "danger", "info"] as Tone[]).map((tone) => (
                  <StatusDot key={tone} tone={tone} pulse size={10} />
                ))}
                <Spinner size={20} className="text-brand" />
              </Specimen>
              <Specimen label="Avatar · Monograma · Bandera">
                <SofiaAvatar size={40} />
                <SofiaAvatar size={40} thinking />
                <Avatar label="Ana Demo" size={40} />
                <Avatar icon="headset" tone="accent" size={40} />
                {["Rappi", "Liverpool", "Netflix", "Cinépolis"].map((m) => (
                  <MerchantMonogram key={m} name={m} />
                ))}
                <Flag country="MX" size={18} />
                <Flag country="CO" size={18} />
                <Flag country="AR" size={18} />
              </Specimen>
              <Specimen label="Meter (con umbral) · Input · Skeleton">
                <div className="w-full space-y-3">
                  <Meter value={0.91} threshold={0.55} label="Confianza 91 %" />
                  <Meter value={0.42} threshold={0.55} tone="warn" label="Confianza 42 %" />
                  <Input icon="id-card" placeholder="MX-DEMO-001" className="font-mono" />
                  <div className="space-y-2">
                    <Skeleton className="h-3 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              </Specimen>
            </div>
          </Section>

          <Section id="moleculas" eyebrow="Nivel 2" title="Moléculas">
            <div className="grid gap-3 lg:grid-cols-2">
              <Specimen label="Segmented · LanguageToggle">
                <Segmented
                  value={segment}
                  onChange={setSegment}
                  label="Ejemplo"
                  options={[
                    { value: "a", label: "Todos" },
                    { value: "b", label: "ES" },
                    { value: "c", label: "PT" },
                  ]}
                />
                <LanguageToggle lang={lang} onChange={setLang} />
              </Specimen>
              <Specimen label="OtpInput · SmsToast">
                <OtpDemo />
                <div className="w-full max-w-sm">
                  <SmsToast code="482913" lang={lang} onUse={() => undefined} />
                </div>
              </Specimen>
              <Specimen label="Stepper · LayerTrack">
                <Stepper
                  steps={[
                    { label: "Documento", state: "done" },
                    { label: "Código", state: "current" },
                    { label: "Chat", state: "upcoming" },
                  ]}
                />
                <LayerTrackDemo />
              </Specimen>
              <Specimen label="RouteBadge · PolicyLadder">
                <div className="flex flex-wrap gap-1.5">
                  {ROUTES.map((route) => (
                    <RouteBadge key={route} route={route} lang={lang} />
                  ))}
                </div>
                <div className="w-full space-y-2">
                  <PolicyLadder ruleId="POL-5" route="auto" />
                  <PolicyLadder ruleId="POL-6" route="human" />
                  <PolicyLadder ruleId="POL-3" route="deny" />
                </div>
              </Specimen>
              <Specimen label="CustomerTile">
                <div className="grid w-full gap-2 sm:grid-cols-2">
                  <CustomerTile customer={{ document_number: "MX-DEMO-001", label: "Ana · MX · demo", country: "MX", role: "customer" }} selected onSelect={() => undefined} />
                  <CustomerTile customer={{ document_number: "AGENTE-DEMO", label: "Agente humano · consola", country: "MX", role: "agent" }} selected={false} onSelect={() => undefined} />
                </div>
              </Specimen>
              <Specimen label="CandidateOption · QuickReplies">
                <div className="w-full space-y-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <CandidateOption card={{ option: 1, transaction_id: "TX-MX-0002", date: "12 de septiembre de 2026", merchant: "Cinépolis", amount: "189.00", currency: "MXN", amount_display: "$189.00 MXN" }} lang={lang} disabled={false} onSelect={() => undefined} />
                    <CandidateOption card={{ option: 2, transaction_id: "TX-MX-0003", date: "12 de septiembre de 2026", merchant: "Cinépolis", amount: "189.00", currency: "MXN", amount_display: "$189.00 MXN" }} lang={lang} disabled={false} onSelect={() => undefined} index={1} />
                  </div>
                  <QuickReplies replies={["Sí, confirmo", "No"]} onReply={() => undefined} />
                </div>
              </Specimen>
              <Specimen label="TransactionTicket">
                <div className="w-full">
                  <TransactionTicket card={{ transaction_id: "TX-MX-0001", date: "20 de septiembre de 2026", merchant: "Rappi", amount: "349.00", currency: "MXN", amount_display: "$349.00 MXN" }} lang={lang} />
                </div>
              </Specimen>
              <Specimen label="CaseReceipt (REQ-09)">
                <div className="w-full">
                  <CaseReceipt
                    lang={lang}
                    card={{ dispute_id: "DSP-2026-000901", status: "open", status_display: "abierta", verified: true }}
                    subject={{ transaction_id: "TX-MX-0001", date: "20 de septiembre de 2026", merchant: "Rappi", amount: "349.00", currency: "MXN", amount_display: "$349.00 MXN" }}
                  />
                </div>
              </Specimen>
              <Specimen label="HandoffNotice">
                <div className="w-full">
                  <HandoffNotice handoff={SAMPLE_HANDOFF} lang={lang} />
                </div>
              </Specimen>
              <Specimen label="FactRow · ActionRow · JsonView">
                <div className="w-full space-y-3">
                  <ul>
                    <FactRow fact="Monto 349.00 MXN (≈ 19.30 USD)" source="GET /transactions/TX-MX-0001" />
                  </ul>
                  <ol>
                    <ActionRow action="create_dispute" result="DSP-2026-000901" verified last={false} />
                    <ActionRow action="verify_dispute" result="GET /disputes/DSP-2026-000901 → open" verified last index={1} />
                  </ol>
                  <JsonView value={{ code: "rule_applied", params: { rule_id: "POL-5", route: "auto" }, duration_ms: 44, ok: true }} />
                </div>
              </Specimen>
            </div>
          </Section>

          <Section id="graficas" eyebrow="Visualización" title="Gráficas propias en SVG">
            <p className="-mt-3 max-w-2xl text-sm text-ink-3">
              Marcas finas (líneas de 2 px, barras de hasta 24 px con punta redondeada de 4 px), 2 px de aire entre segmentos, texto siempre en tinta y
              tooltip al pasar el cursor. Las series pasan el validador de paleta (daltonismo, contraste y luminosidad) en ambos temas.
            </p>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              <StatTile label="Latencia por turno" value={480} format={(v) => `${Math.round(v)} ms`} icon="activity">
                <Sparkline
                  data={[420, 380, 510, 460, 390, 350, 480].map((value, i) => ({ label: `Turno ${i + 1}`, value }))}
                  label="Latencia por turno, estable entre 350 y 510 ms"
                  format={(v) => `${v} ms`}
                />
              </StatTile>
              <StatTile label="Llegadas (última hora)" value={14} icon="inbox">
                <ColumnChart
                  data={[0, 1, 0, 2, 1, 3, 1, 0, 2, 1, 2, 1].map((value, i) => ({ label: `franja ${i + 1}`, value }))}
                  label="Llegadas por franja de 5 minutos"
                />
              </StatTile>
              <StatTile label="Completitud de la ficha" icon="shield-check">
                <div className="flex items-center gap-4">
                  <RingGauge value={5} max={6} label="5 de 6 campos">
                    <span className="text-lg font-semibold text-ink">
                      5<span className="text-xs text-ink-3">/6</span>
                    </span>
                  </RingGauge>
                  <p className="text-xs leading-relaxed text-ink-3">Anillo que se dibuja desde las 12 en punto.</p>
                </div>
              </StatTile>
              <StatTile label="Motivo de transferencia" icon="flag">
                <BarList
                  label="Casos por motivo"
                  items={[
                    { key: "POL-6", label: "Revisión por política", value: 6, icon: "layer-decide" },
                    { key: "customer_request", label: "Pidió una persona", value: 4, icon: "headset" },
                    { key: "POL-7", label: "Transacción no identificada", value: 2, icon: "layer-decide" },
                  ]}
                />
              </StatTile>
              <StatTile label="Idioma del cliente" icon="globe">
                <SplitBar
                  label="Casos por idioma"
                  segments={[
                    { key: "es", label: "Español", value: 9, series: "series-1" },
                    { key: "pt", label: "Português", value: 5, series: "series-2" },
                  ]}
                />
              </StatTile>
              <Card className="p-4">
                <TurnWaterfall events={SAMPLE_EVENTS} lang={lang} />
              </Card>
            </div>
          </Section>

          <Section id="organismos" eyebrow="Nivel 3" title="Organismos">
            <p className="-mt-3 max-w-2xl text-sm text-ink-3">
              La ficha de la consola completa: encabezado con completitud, hechos con su fuente, acciones verificadas, preguntas como checklist y
              el feedback del agente humano (LEARN), que vuelve a la traza como score.
            </p>
            <HandoffSheet handoff={SAMPLE_HANDOFF} now={now} feedback={demoFeedback} onFeedback={sendDemoFeedback} />
          </Section>

          <Section id="movimiento" eyebrow="Fundamentos" title="Movimiento">
            <div className="flex flex-wrap items-center gap-3">
              <Badge mono>ease-out-soft · cubic-bezier(.22, 1, .36, 1)</Badge>
              <Badge mono>ease-spring · cubic-bezier(.34, 1.56, .64, 1)</Badge>
              <Badge mono>150–460 ms</Badge>
              <Badge tone="ok" icon="check">
                respeta prefers-reduced-motion
              </Badge>
              <Button size="sm" variant="secondary" icon="refresh" onClick={() => setReplay((r) => r + 1)}>
                Repetir
              </Button>
            </div>
            <div key={replay} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { name: "rise", className: "animate-rise" },
                { name: "pop", className: "animate-pop" },
                { name: "slide-down", className: "animate-slide-down" },
                { name: "grow-x", className: "origin-left animate-grow-x" },
                { name: "shake", className: "animate-shake" },
                { name: "bob", className: "animate-bob rounded-full bg-fig-sun" },
                { name: "turn", className: "animate-turn rounded-tl-full bg-fig-coral" },
                { name: "morph", className: "animate-morph bg-fig-ink" },
                { name: "breathe", className: "animate-breathe rounded-full" },
                { name: "ping-soft", className: "" },
              ].map((motion) => (
                <Card key={motion.name} className="flex flex-col items-center gap-3 p-5">
                  <span className="relative grid size-12 place-items-center">
                    {motion.name === "ping-soft" && <span className="absolute inset-0 animate-ping-soft rounded-xl bg-brand" />}
                    <span className={cn("relative size-12 rounded-xl bg-brand", motion.className)} />
                  </span>
                  <Mono className="text-xs text-ink-2">{motion.name}</Mono>
                </Card>
              ))}
            </div>
          </Section>
        </main>
      </div>
    </div>
  );
}
