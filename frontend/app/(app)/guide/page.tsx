import type { Metadata } from "next";
import { GuideView } from "@/components/views/GuideView";

export const metadata: Metadata = { title: "How it works" };

export default function GuidePage() {
  return <GuideView />;
}
