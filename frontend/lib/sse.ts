/**
 * Live stream client for GET /live/:id (Server-Sent Events).
 *
 * The orchestrator sends one JSON-encoded `LiveEvent` per SSE message.
 * EventSource reconnects on its own; we only surface the connection state.
 */
import { liveUrl } from "./api";
import { config } from "./config";
import { mockBackend } from "./mock/backend";
import type { LiveEvent } from "./types";

export type ConnectionState = "connecting" | "open" | "reconnecting";

export interface LiveHandlers {
  onEvent: (event: LiveEvent) => void;
  onConnection?: (state: ConnectionState) => void;
}

/** Subscribe to an experiment's live events. Returns an unsubscribe function. */
export function subscribeLive(experimentId: string, handlers: LiveHandlers): () => void {
  if (config.useMock) {
    handlers.onConnection?.("open");
    return mockBackend.subscribe(experimentId, handlers.onEvent);
  }

  handlers.onConnection?.("connecting");
  const source = new EventSource(liveUrl(experimentId));

  source.onopen = () => handlers.onConnection?.("open");
  source.onerror = () => handlers.onConnection?.("reconnecting");
  source.onmessage = (msg) => {
    try {
      handlers.onEvent(JSON.parse(msg.data) as LiveEvent);
    } catch {
      console.warn("[sse] dropped malformed event", msg.data);
    }
  };

  return () => source.close();
}
