import type { Metadata } from "next";
import { Suspense } from "react";
import { Loading } from "@/components/ui/StateBlock";
import { ExperimentRoute } from "./ExperimentRoute";

export const metadata: Metadata = { title: "Experiment" };

/** /experiments/:id — live grid while running, full report when done. */
export default function ExperimentPage() {
  // The id is only known at request time; useParams needs a Suspense boundary under cacheComponents.
  return (
    <Suspense fallback={<Loading label="LOADING EXPERIMENT" />}>
      <ExperimentRoute />
    </Suspense>
  );
}
