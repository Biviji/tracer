import Link from "next/link";
import { Suspense } from "react";
import { NavLinks, NavLinksFallback } from "./NavLinks";

/** Left rail on desktop, top bar under 860px. */
export function Rail() {
  return (
    <nav
      aria-label="Main"
      className="flex flex-wrap items-center gap-y-1.5 border-b-[3px] border-black bg-rail py-3 text-rail-ink desk:sticky desk:top-0 desk:h-dvh desk:flex-col desk:flex-nowrap desk:items-stretch desk:border-r-[3px] desk:border-b-0 desk:py-5"
    >
      <Link href="/" className="flex items-center gap-2 px-3.5 desk:px-[18px] desk:pb-1">
        <span className="relative size-4 shrink-0" aria-hidden>
          <i className="absolute top-0 left-0 size-[7px] bg-accent" />
          <i className="absolute right-0 bottom-0 size-[7px] bg-rail-ink" />
        </span>
        <b className="font-display text-lg font-extrabold tracking-[.02em]">
          TRACE<span className="text-accent">.</span>
        </b>
      </Link>
      <div className="hidden px-[18px] pt-0.5 pb-[22px] text-[10px] leading-[1.7] tracking-[.22em] text-rail-muted desk:block">
        AGENT
        <br />
        RELIABILITY
        <br />
        LAB
      </div>

      <div className="ml-auto desk:ml-0">
        <Suspense fallback={<NavLinksFallback />}>
          <NavLinks />
        </Suspense>
      </div>

      <div className="mt-auto hidden items-center gap-2 px-[18px] pt-4 text-[10px] tracking-[.14em] text-rail-muted desk:flex">
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
          <path d="M3 4h7l4 16h-5L3 4z" fill="currentColor" />
        </svg>
        <span>
          RUNNING ON
          <br />
          VULTR
        </span>
      </div>
    </nav>
  );
}
