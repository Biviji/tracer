import Link from "next/link";
import { errorMessage } from "@/lib/errors";

/** Loading / error / empty placeholders with the brutalist frame. */

export function Loading({ label = "LOADING" }: { label?: string }) {
  return (
    <div className="my-6 border-2 border-dashed border-line p-6 text-[11px] tracking-[.2em] text-muted" role="status">
      {label}…
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="my-6 flex flex-wrap items-center justify-between gap-3 border-2 border-fail-line bg-fail-bg p-4" role="alert">
      <div>
        <b className="font-display tracking-[.03em] text-fail-line">REQUEST FAILED</b>
        <p className="mt-1 text-[11.5px] text-muted">{errorMessage(error)}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost">
          RETRY
        </button>
      )}
    </div>
  );
}

export function Empty({ title, body, cta }: { title: string; body: string; cta?: { href: string; label: string } }) {
  return (
    <div className="my-6 border-2 border-line bg-card p-6">
      <h3 className="text-lg uppercase">{title}</h3>
      <p className="mt-1 text-muted">{body}</p>
      {cta && (
        <Link href={cta.href} className="btn-ghost mt-4 inline-block">
          {cta.label}
        </Link>
      )}
    </div>
  );
}
