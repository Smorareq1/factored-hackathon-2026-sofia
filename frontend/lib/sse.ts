// SSE sobre POST: EventSource solo soporta GET, así que se lee el stream de fetch y se parsea a mano.
import { AGENT_URL } from "./api";
import type { AgentMessage, Handoff, Language, LayerEvent, SystemVersion, TurnDone, TurnError } from "./types";

export type ChatEvent =
  | { event: "layer"; data: LayerEvent }
  | { event: "message"; data: AgentMessage }
  | { event: "handoff"; data: Handoff }
  | { event: "done"; data: TurnDone }
  | { event: "error"; data: TurnError };

export interface ChatTurnRequest {
  token: string;
  threadId: string;
  message: string;
  languageHint: Language;
  systemVersion?: SystemVersion;
  signal?: AbortSignal;
}

export async function streamChat(req: ChatTurnRequest, onEvent: (event: ChatEvent) => void): Promise<void> {
  const response = await fetch(`${AGENT_URL}/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${req.token}` },
    body: JSON.stringify({
      thread_id: req.threadId,
      message: req.message,
      language_hint: req.languageHint,
      system_version: req.systemVersion ?? "proposed",
    }),
    signal: req.signal,
  });
  if (response.status === 401) {
    onEvent({ event: "error", data: { code: "session_expired", message: "reauth" } });
    return;
  }
  if (!response.ok || !response.body) {
    onEvent({ event: "error", data: { code: `http_${response.status}`, message: response.statusText } });
    return;
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseBlock(block);
      if (parsed) onEvent(parsed);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

function parseBlock(block: string): ChatEvent | null {
  let name: string | null = null;
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!name || data.length === 0) return null; // pings y comentarios
  return { event: name, data: JSON.parse(data.join("\n")) } as ChatEvent;
}
