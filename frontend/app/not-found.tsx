import { Empty } from "@/components/ui/StateBlock";

export default function NotFound() {
  return <Empty title="404 — Not found" body="This page does not exist." cta={{ href: "/", label: "BACK TO EXPERIMENTS" }} />;
}
