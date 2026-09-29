"use client";

// Consola del agente humano: tablero de la cola + ficha §9.4. Sin transcript, por diseño (REQ-05).
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Avatar } from "@/components/atoms/avatar";
import { IconButton } from "@/components/atoms/button";
import { StatusDot } from "@/components/atoms/status-dot";
import { Brand } from "@/components/molecules/brand";
import { EmptyState } from "@/components/molecules/stat-tile";
import { HandoffQueue } from "@/components/organisms/handoff-queue";
import { HandoffSheet } from "@/components/organisms/handoff-sheet";
import { QueueOverview } from "@/components/organisms/queue-overview";
import { AppHeader, WorkspaceShell } from "@/components/templates/shells";
import { api } from "@/lib/api";
import { useNow } from "@/lib/hooks";
import { clearSession, loadSession } from "@/lib/session";
import type { Handoff, HandoffFeedback, HandoffFeedbackRecord } from "@/lib/types";

const POLL_MS = 10_000;

export default function ConsoleScreen() {
  const router = useRouter();
  const [session] = useState(() => loadSession());
  const [queue, setQueue] = useState<Handoff[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);
  // Feedback por ficha (LEARN): ausente = sin cargar, null = nadie la calificó todavía.
  const [feedback, setFeedback] = useState<Record<string, HandoffFeedbackRecord | null>>({});
  const known = useRef<Set<string> | null>(null);
  const now = useNow(15_000);

  // Casos que llegaron desde la última lectura: se marcan "nuevo" hasta que el agente los abre.
  function apply(items: Handoff[]) {
    const ids = items.map((h) => h.handoff_id);
    const previous = known.current;
    if (previous) {
      const added = ids.filter((id) => !previous.has(id));
      if (added.length) setFresh((prev) => new Set([...prev, ...added]));
    }
    known.current = new Set(ids);
    setQueue(items);
  }

  useEffect(() => {
    if (!session || session.role !== "agent") {
      router.replace("/");
      return;
    }
    const poll = () =>
      api.handoffs(session.token).then(
        (list) => apply(list.items),
        () => router.replace("/"),
      );
    poll();
    const id = window.setInterval(poll, POLL_MS);
    return () => window.clearInterval(id);
  }, [session, router]);

  const selected = queue.find((h) => h.handoff_id === selectedId) ?? queue[0];
  const selectedKey = selected?.handoff_id;
  useEffect(() => {
    if (!session || !selectedKey || selectedKey in feedback) return;
    api.feedback(session.token, selectedKey).then(
      (record) => setFeedback((prev) => ({ ...prev, [selectedKey]: record })),
      () => setFeedback((prev) => ({ ...prev, [selectedKey]: null })),
    );
  }, [session, selectedKey, feedback]);

  if (!session) return null;

  async function sendFeedback(id: string, body: HandoffFeedback) {
    if (!session) return;
    const record = await api.sendFeedback(session.token, id, body);
    setFeedback((prev) => ({ ...prev, [id]: record }));
  }

  function refresh() {
    if (!session) return;
    setRefreshing(true);
    api
      .handoffs(session.token)
      .then((list) => apply(list.items))
      .finally(() => window.setTimeout(() => setRefreshing(false), 400));
  }

  function select(id: string) {
    setSelectedId(id);
    setFresh((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  return (
    <WorkspaceShell
      header={
        <AppHeader
          left={
            <>
              <Brand lang="es" compact />
              <span className="hidden h-6 w-px bg-line sm:block" />
              <div className="hidden sm:block">
                <p className="text-sm font-bold text-ink">Consola de agentes</p>
                <p className="flex items-center gap-1.5 text-[11px] text-ink-3">
                  <StatusDot tone="ok" pulse size={6} />
                  En vivo · se actualiza cada {POLL_MS / 1000} s
                </p>
              </div>
            </>
          }
          right={
            <>
              <div className="hidden items-center gap-2 rounded-full bg-surface-2 py-1 pr-3 pl-1 md:flex">
                <Avatar icon="headset" tone="accent" size={28} />
                <span className="text-xs font-semibold text-ink">{session.label.split(" · ")[0]}</span>
              </div>
              <IconButton icon="refresh" label="Actualizar la cola" onClick={refresh} spinning={refreshing} />
              <IconButton
                icon="logout"
                label="Salir"
                onClick={() => {
                  clearSession();
                  router.replace("/");
                }}
              />
            </>
          }
        />
      }
    >
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="max-h-[42vh] border-b border-line bg-surface-2 lg:max-h-none lg:w-[350px] lg:shrink-0 lg:border-r lg:border-b-0">
          <HandoffQueue queue={queue} selectedId={selected?.handoff_id ?? null} fresh={fresh} now={now} onSelect={select} />
        </div>
        <div className="scrollbar-thin min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
            <QueueOverview queue={queue} now={now} />
            {selected ? (
              <HandoffSheet
                key={selected.handoff_id}
                handoff={selected}
                now={now}
                feedback={feedback[selected.handoff_id]}
                onFeedback={(body) => sendFeedback(selected.handoff_id, body)}
              />
            ) : (
              <EmptyState
                icon="headset"
                title="Sin casos para atender"
                body="Cuando Sofía transfiera una conversación, vas a ver aquí la ficha con los hechos verificados y su fuente."
                className="py-16"
              />
            )}
          </div>
        </div>
      </div>
    </WorkspaceShell>
  );
}
