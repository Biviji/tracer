"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { forgetOwner, useOwnerToken } from "@/lib/owner";

/** Shown only in the browser that started the experiment. Two clicks, no browser dialog. */
export function DeleteExperiment({ id }: { id: string }) {
  const token = useOwnerToken(id);
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) return null;

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteExperiment(id, token!);
      forgetOwner(id);
      router.push("/reports");
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <section className="mt-4 flex flex-wrap items-center gap-3 border-2 border-line bg-card px-4 py-3 text-[12px]">
      <span className="min-w-0 flex-1 text-muted">
        You started this experiment. Its task, outputs and diffs are deleted automatically after 30 days, or now if you
        prefer.{" "}
        <Link href="/privacy" className="underline hover:text-accent">
          Privacy
        </Link>
      </span>
      {confirming ? (
        <span className="flex items-center gap-2">
          <span className="text-fail-line">Delete for everyone? This can&apos;t be undone.</span>
          <button type="button" className="btn-ghost" onClick={() => setConfirming(false)} disabled={busy}>
            KEEP
          </button>
          <button type="button" className="btn-ghost border-fail-line text-fail-line" onClick={remove} disabled={busy}>
            {busy ? "DELETING…" : "DELETE"}
          </button>
        </span>
      ) : (
        <button type="button" className="btn-ghost" onClick={() => setConfirming(true)}>
          DELETE EXPERIMENT
        </button>
      )}
      {error && <span className="w-full text-fail-line">{error}</span>}
    </section>
  );
}
