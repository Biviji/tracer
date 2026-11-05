import type { Metadata } from "next";
import { ExperimentForm } from "@/components/views/ExperimentForm";

export const metadata: Metadata = { title: "New experiment" };

/** Experiment config. Launching redirects to /experiments/:id for the live run. */
export default function NewExperimentPage() {
  return <ExperimentForm />;
}
