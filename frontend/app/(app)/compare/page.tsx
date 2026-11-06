import type { Metadata } from "next";
import { Suspense } from "react";
import { Loading } from "@/components/ui/StateBlock";
import { CompareView } from "@/components/views/CompareView";

export const metadata: Metadata = { title: "Compare" };

export default function ComparePage() {
  // CompareView reads ?exp=&a=&b= via useSearchParams, which needs a Suspense boundary.
  return (
    <Suspense fallback={<Loading />}>
      <CompareView />
    </Suspense>
  );
}
