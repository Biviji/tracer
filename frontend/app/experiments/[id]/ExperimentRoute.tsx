"use client";

import { useParams } from "next/navigation";
import { ExperimentView } from "@/components/views/ExperimentView";

export function ExperimentRoute() {
  const { id } = useParams<{ id: string }>();
  return <ExperimentView id={decodeURIComponent(id)} />;
}
