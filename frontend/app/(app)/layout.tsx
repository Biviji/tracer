import { Rail } from "@/components/layout/Rail";

/** The app shell: left rail (top bar on small screens) + content. The landing page at / has none. */
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="grid min-h-dvh grid-cols-1 bg-ink desk:grid-cols-[200px_1fr]">
      <Rail />
      <main className="min-w-0 bg-paper px-4 pt-[22px] pb-10 sm:px-5">{children}</main>
    </div>
  );
}
