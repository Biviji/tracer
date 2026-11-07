import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/PageHeader";

export const metadata: Metadata = { title: "Privacy" };

const SECTIONS: { h: string; p: React.ReactNode }[] = [
  {
    h: "What is stored",
    p: "For each experiment: the repository URL, the task, the check command, the models chosen, and what every run produced (its steps, the code it changed, the check output, time and tokens). Nothing else. There are no accounts.",
  },
  {
    h: "Who can see it",
    p: "Experiments are public to everyone using this site: they appear under Reports and Overview. Use public repositories only, and never put secrets, API keys or personal data in the task.",
  },
  {
    h: "Where your code goes",
    p: "Each run clones the repository into a fresh, offline sandbox on a Vultr VM. The agent's prompts, including parts of your code, are sent to the chosen model on Vultr Serverless Inference. Sandboxes and their copies of the code are destroyed when the run ends.",
  },
  {
    h: "How long it's kept",
    p: "Finished experiments are deleted automatically after 30 days. The browser that started an experiment can delete it sooner from its report page.",
  },
  {
    h: "Cookies and tracking",
    p: "None. No cookies, no analytics, no ads. Your browser keeps two small notes in local storage: whether you've seen the form tour, and the keys that let you stop or delete experiments you started. Your IP address is used only in memory to apply the hourly run limit, and is never stored.",
  },
  {
    h: "No guarantees",
    p: "TRACE is a hackathon project (Vultr Track 01). Results come from AI models and can be wrong; the service may change or go away without notice.",
  },
];

export default function PrivacyPage() {
  return (
    <>
      <PageHeader
        eyebrow="PRIVACY"
        title={["YOUR DATA"]}
        lede="Short version: experiments are public, kept for 30 days, and nothing tracks you."
      />
      <div className="mt-6 grid max-w-[78ch] gap-0 border-2 border-line bg-card">
        {SECTIONS.map((s) => (
          <section key={s.h} className="border-b-2 border-line px-5 py-4 last:border-0">
            <h2 className="mb-1.5 font-display text-[15px] font-extrabold tracking-[.04em] uppercase">{s.h}</h2>
            <p className="leading-relaxed text-muted">{s.p}</p>
          </section>
        ))}
      </div>
    </>
  );
}
