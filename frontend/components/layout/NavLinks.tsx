"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  {
    href: "/experiments",
    label: "EXPERIMENTS",
    match: (p: string) => p.startsWith("/experiments") || p.startsWith("/new"),
  },
  {
    href: "/overview",
    label: "OVERVIEW",
    match: (p: string) => p.startsWith("/overview"),
  },
  {
    href: "/compare",
    label: "COMPARE",
    match: (p: string) => p.startsWith("/compare"),
  },
  {
    href: "/reports",
    label: "REPORTS",
    match: (p: string) => p.startsWith("/reports"),
  },
] as const;

/** Fixed-size bar that grows while this link's page is loading. */
function PendingBar() {
  const { pending } = useLinkStatus();
  return <span aria-hidden className={`nav-pending ${pending ? "is-pending" : ""}`} />;
}

function NavList({ pathname }: { pathname: string | null }) {
  return (
    <ul className="flex flex-wrap gap-0.5 px-2 desk:flex-col desk:px-2.5">
      {ITEMS.map((item) => {
        const active = pathname !== null && item.match(pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`relative flex items-center gap-2 border px-2.5 py-2 text-xs tracking-[.08em] desk:py-[11px] ${
                active ? "border-black bg-paper text-ink" : "border-transparent text-[#CFCCC4] hover:text-white"
              }`}
            >
              <span className="text-accent">/</span> {item.label}
              <PendingBar />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Active-state nav. Reads the pathname, so it must sit inside <Suspense>. */
export function NavLinks() {
  return <NavList pathname={usePathname()} />;
}

/** Static fallback rendered during prerender (no active item). */
export function NavLinksFallback() {
  return <NavList pathname={null} />;
}
