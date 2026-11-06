import { Loading } from "@/components/ui/StateBlock";

/** Shown instantly while an app page loads. */
export default function AppLoading() {
  return (
    <div className="page-enter max-w-[720px]">
      <div className="skeleton mb-3 h-3 w-40" />
      <div className="skeleton mb-2 h-12 w-3/4" />
      <div className="skeleton h-12 w-1/2" />
      <Loading label="LOADING PAGE" rows={4} />
    </div>
  );
}
