import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders model output (Markdown) safely: raw HTML in the text is NOT rendered,
 * only Markdown. Wide content (tables, code) scrolls inside its own box so it
 * can never push the page sideways; long unbroken words wrap.
 */
const components: Components = {
  h1: ({ children }) => <h4 className="mt-3 mb-1.5 font-display text-[15px] font-extrabold first:mt-0">{children}</h4>,
  h2: ({ children }) => <h4 className="mt-3 mb-1.5 font-display text-[14px] font-extrabold first:mt-0">{children}</h4>,
  h3: ({ children }) => <h5 className="mt-2.5 mb-1 font-display text-[13px] font-extrabold first:mt-0">{children}</h5>,
  h4: ({ children }) => <h5 className="mt-2.5 mb-1 font-display text-[13px] font-extrabold first:mt-0">{children}</h5>,
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-2 list-disc pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal pl-5">{children}</ol>,
  li: ({ children }) => <li className="my-0.5">{children}</li>,
  strong: ({ children }) => <strong className="font-bold text-ink">{children}</strong>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer noopener" className="underline underline-offset-2 hover:text-accent">
      {children}
    </a>
  ),
  code: ({ children, className }) =>
    className ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="border border-line bg-paper px-1 py-px text-[0.95em]">{children}</code>
    ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto border-[1.5px] border-line bg-paper p-2.5 text-[11.5px] leading-relaxed [&_code]:border-0 [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-[11.5px]">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-[1.5px] border-line px-2 py-1 text-left font-bold whitespace-nowrap">{children}</th>
  ),
  td: ({ children }) => <td className="border-[1.5px] border-line px-2 py-1 align-top">{children}</td>,
  blockquote: ({ children }) => <blockquote className="my-2 border-l-4 border-line pl-3 text-muted">{children}</blockquote>,
  hr: () => <hr className="my-3 border-0 border-t-2 border-dotted border-line" />,
};

export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  return (
    <div className={`min-w-0 text-[12.5px] leading-relaxed [overflow-wrap:anywhere] ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
