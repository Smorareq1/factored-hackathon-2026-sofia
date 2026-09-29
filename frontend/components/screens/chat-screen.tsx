"use client";

// Chat del cliente + caja de cristal. Solo en el cliente: la sesión de la demo vive en sessionStorage.
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/atoms/avatar";
import { Button, IconButton } from "@/components/atoms/button";
import { Flag } from "@/components/atoms/flag";
import { Icon } from "@/components/atoms/icon";
import { SofiaMark } from "@/components/atoms/logo";
import { StatusDot } from "@/components/atoms/status-dot";
import { Brand } from "@/components/molecules/brand";
import { LanguageToggle, Segmented } from "@/components/molecules/segmented";
import { type ChatItem, ChatThread } from "@/components/organisms/chat-thread";
import { Composer } from "@/components/organisms/composer";
import { GlassBox, type TurnTrace } from "@/components/organisms/glass-box";
import { AppHeader, WorkspaceShell } from "@/components/templates/shells";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import { clearSession, loadSession, newThreadId, type StoredSession, updateSession } from "@/lib/session";
import { streamChat } from "@/lib/sse";
import type { AgentMeta, Language, Layer, SystemVersion } from "@/lib/types";

const uid = () => crypto.randomUUID();

function upsertTurn(traces: TurnTrace[], turn: number, update: (trace: TurnTrace) => TurnTrace): TurnTrace[] {
  const existing = traces.find((tr) => tr.turn === turn) ?? { turn, events: [] };
  return [...traces.filter((tr) => tr.turn !== turn), update(existing)];
}

export default function ChatScreen() {
  const router = useRouter();
  const [session, setSession] = useState<StoredSession | null>(() => loadSession());
  const [lang, setLang] = useState<Language>(() => session?.language ?? "es");
  const [items, setItems] = useState<ChatItem[]>([]);
  const [traces, setTraces] = useState<TurnTrace[]>([]);
  const [busy, setBusy] = useState(false);
  const [activeLayer, setActiveLayer] = useState<Layer | null>(null);
  const [seenLayers, setSeenLayers] = useState<Layer[]>([]);
  const [reauth, setReauth] = useState(false);
  const [meta, setMeta] = useState<AgentMeta | null>(null);
  const [showGlass, setShowGlass] = useState(() => window.matchMedia("(min-width: 1024px)").matches);
  const system: SystemVersion = session?.system ?? "proposed";

  useEffect(() => {
    if (!session || session.role !== "customer") {
      router.replace("/");
      return;
    }
    api.meta().then(setMeta, () => undefined);
    // El baseline no tiene checkpointer: sus hilos no se recuperan al recargar.
    if (session.system === "baseline") return;
    api.thread(session.token, session.threadId).then(
      (snapshot) => setItems(snapshot.messages.map((m) => ({ id: uid(), role: m.role, text: m.text, turn: m.turn }))),
      (err) => {
        if (err instanceof ApiError && err.status === 401) setReauth(true);
      },
    );
  }, [session, router]);

  if (!session) return null;
  const name = session.label.split(" · ")[0];

  function changeLanguage(next: Language) {
    setLang(next);
    setSession(updateSession({ language: next }));
  }

  function newConversation() {
    setItems([]);
    setTraces([]);
    setSession(updateSession({ threadId: newThreadId() }));
  }

  // Sofía ↔ baseline §8.7: cada sistema arranca un hilo propio para comparar la misma conversación.
  function changeSystem(next: SystemVersion) {
    if (next === system || busy) return;
    setItems([]);
    setTraces([]);
    setReauth(false);
    setSession(updateSession({ system: next, threadId: newThreadId() }));
  }

  function logout() {
    clearSession();
    router.replace("/");
  }

  async function send(text: string) {
    if (!session || busy || reauth) return;
    setItems((prev) => [...prev, { id: uid(), role: "customer", text, turn: 0 }]);
    setBusy(true);
    setActiveLayer(null);
    setSeenLayers([]);
    let turn = 0;
    try {
      const request = { token: session.token, threadId: session.threadId, message: text, languageHint: lang, systemVersion: system };
      await streamChat(request, (ev) => {
        switch (ev.event) {
          case "layer":
            turn = ev.data.turn;
            // El baseline no tiene capas: su evento de modo va en GOVERN pero no se ilumina como si verificara.
            if (system === "proposed") {
              setActiveLayer(ev.data.layer);
              setSeenLayers((prev) => (prev.includes(ev.data.layer) ? prev : [...prev, ev.data.layer]));
            }
            setTraces((prev) => upsertTurn(prev, turn, (tr) => ({ ...tr, events: [...tr.events, ev.data] })));
            break;
          case "message":
            setItems((prev) => [...prev, { id: uid(), role: "agent", text: ev.data.text, turn, message: ev.data }]);
            break;
          case "handoff":
            setItems((prev) => {
              const index = prev.findLastIndex((item) => item.role === "agent");
              return index < 0 ? prev : prev.map((item, i) => (i === index ? { ...item, handoff: ev.data } : item));
            });
            break;
          case "done":
            setTraces((prev) => upsertTurn(prev, ev.data.turn, (tr) => ({ ...tr, done: ev.data })));
            if (ev.data.route === "reauth") setReauth(true);
            break;
          case "error":
            if (ev.data.code === "session_expired") setReauth(true);
            else setItems((prev) => [...prev, { id: uid(), role: "error", text: t(lang, "errorGeneric"), turn }]);
            break;
        }
      });
    } catch {
      setItems((prev) => [...prev, { id: uid(), role: "error", text: t(lang, "errorGeneric"), turn }]);
    } finally {
      setBusy(false);
      setActiveLayer(null);
    }
  }

  return (
    <WorkspaceShell
      asideOpen={showGlass}
      onCloseAside={() => setShowGlass(false)}
      aside={<GlassBox turns={traces} lang={lang} meta={meta} onClose={() => setShowGlass(false)} />}
      header={
        <AppHeader
          left={
            <>
              <Brand lang={lang} compact />
              <div className="hidden items-center gap-2.5 rounded-full bg-surface-2 py-1 pr-3 pl-1 md:flex">
                <span className="relative">
                  <Avatar label={name} size={28} />
                  {session.country && (
                    <span className="absolute -right-1 -bottom-0.5 rounded-[3px] bg-surface p-px">
                      <Flag country={session.country} size={9} />
                    </span>
                  )}
                </span>
                <span className="text-xs font-semibold text-ink">{name}</span>
                <span className="flex items-center gap-1.5 text-[11px] text-ink-3">
                  <StatusDot tone="ok" pulse size={7} />
                  {t(lang, "online")}
                </span>
              </div>
            </>
          }
          right={
            <>
              {meta?.baseline_available && (
                // El contenedor oculta el selector en móvil (el control trae su propio display).
                <div className="hidden sm:block">
                  <Segmented
                    value={system}
                    onChange={changeSystem}
                    label={t(lang, "systemLabel")}
                    options={[
                      {
                        value: "proposed",
                        title: t(lang, "systemProposedHint"),
                        label: (
                          <>
                            <SofiaMark size={14} /> Sofía
                          </>
                        ),
                      },
                      {
                        value: "baseline",
                        title: t(lang, "systemBaselineHint"),
                        label: (
                          <>
                            <Icon name="bolt" size={13} /> Baseline
                          </>
                        ),
                      },
                    ]}
                  />
                </div>
              )}
              <LanguageToggle lang={lang} onChange={changeLanguage} />
              <IconButton icon="chat-plus" label={t(lang, "newConversation")} onClick={newConversation} />
              <IconButton
                icon="glass-box"
                label={t(lang, showGlass ? "glassHide" : "glassShow")}
                pressed={showGlass}
                onClick={() => setShowGlass((v) => !v)}
              />
              <IconButton icon="logout" label={t(lang, "logout")} onClick={logout} />
            </>
          }
        />
      }
    >
      {system === "baseline" && (
        <div role="note" className="flex animate-slide-down items-start gap-2.5 bg-accent px-6 py-2.5 text-sm text-on-accent">
          <Icon name="bolt" size={16} className="mt-0.5 shrink-0" />
          <span>
            <strong>{t(lang, "systemBaselineTitle")}.</strong> {t(lang, "systemBaselineBody")}
          </span>
        </div>
      )}
      {reauth && (
        <div role="alert" className="flex animate-slide-down flex-wrap items-center justify-between gap-3 bg-danger px-6 py-3 text-sm text-white">
          <span className="flex items-center gap-2">
            <Icon name="lock" size={16} />
            <strong>{t(lang, "reauthTitle")}.</strong> {t(lang, "reauthBody")}
          </span>
          <Button variant="secondary" size="sm" icon="key" onClick={logout}>
            {t(lang, "reauthAction")}
          </Button>
        </div>
      )}
      <ChatThread items={items} lang={lang} busy={busy} activeLayer={activeLayer} seenLayers={seenLayers} onReply={send} />
      <Composer lang={lang} disabled={busy || reauth} onSend={send} />
    </WorkspaceShell>
  );
}
