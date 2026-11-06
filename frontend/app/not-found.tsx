import { Empty } from "@/components/ui/StateBlock";

export default function NotFound() {
  return (
    <main className="min-h-dvh bg-paper px-4 pt-[22px] pb-10 sm:px-5">
      <Empty title="404 — Not found" body="This page does not exist." cta={{ href: "/experiments", label: "BACK TO EXPERIMENTS" }} />
    </main>
  );
}
