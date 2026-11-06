import Link from "next/link";
import { errorMessage } from "@/lib/errors";

/** Loading / error / empty placeholders with the brutalist frame. */

/** The brand's two squares chasing each other around a box. */
export function Spinner({ size = 22 }: { size?: number }) {
  return (
    <span className="loader-mark" style={{ width: size, height: size }} aria-hidden>
      <i />
      <i />
    </span>
  );
}

export function Loading({ label = "LOADING", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="my-6 border-2 border-line bg-card" role="status" aria-live="polite">
      <div className="flex items-center gap-3 border-b-2 border-line px-4 py-3">
        <Spinner />
        <span className="text-[11px] tracking-[.2em] text-muted">
          {label}
          <span className="loader-dots" aria-hidden />
        </span>
      </div>
      <div className="loader-bar" aria-hidden />
      <div className="space-y-2.5 p-4" aria-hidden>
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="skeleton h-3" style={{ width: `${92 - i * 17}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div
      className="my-6 flex flex-wrap items-center justify-between gap-3 border-2 border-fail-line bg-fail-bg p-4"
      role="alert"
    >
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
