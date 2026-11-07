/**
 * No accounts: the browser that starts an experiment gets an owner token, kept here in
 * localStorage. It is the only thing that can stop or delete that experiment.
 */
import { useSyncExternalStore } from "react";

const KEY = "trace-owned-v1";
const listeners = new Set<() => void>();

function read(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}") as Record<string, string>;
  } catch {
    return {};
  }
}

function write(map: Record<string, string>) {
  try {
    localStorage.setItem(KEY, JSON.stringify(map));
  } catch {
    /* private mode / storage blocked: the experiment just can't be deleted from this browser */
  }
  listeners.forEach((l) => l());
}

export function rememberOwner(id: string, token: string) {
  write({ ...read(), [id]: token });
}

export function forgetOwner(id: string) {
  const map = read();
  delete map[id];
  write(map);
}

export function ownerToken(id: string): string | null {
  return read()[id] ?? null;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** The owner token for this experiment, or null if this browser didn't start it (null on the server). */
export function useOwnerToken(id: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => ownerToken(id),
    () => null,
  );
}
