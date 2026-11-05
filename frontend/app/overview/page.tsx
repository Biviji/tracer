import type { Metadata } from "next";
import { OverviewView } from "@/components/views/OverviewView";

export const metadata: Metadata = { title: "Overview" };

export default function OverviewPage() {
  return <OverviewView />;
}
