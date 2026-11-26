"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Styled markdown renderer for AI answers (tables, lists, headings, quotes). */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h3 className="text-base font-semibold mt-3" {...p} />,
          h2: (p) => <h3 className="text-base font-semibold mt-3" {...p} />,
          h3: (p) => <h4 className="text-sm font-semibold mt-3 text-foreground" {...p} />,
          h4: (p) => <h5 className="text-sm font-semibold mt-2" {...p} />,
          p: (p) => <p className="leading-relaxed" {...p} />,
          ul: (p) => <ul className="list-disc pl-5 space-y-1" {...p} />,
          ol: (p) => <ol className="list-decimal pl-5 space-y-1" {...p} />,
          strong: (p) => <strong className="font-semibold text-foreground" {...p} />,
          a: ({ href, ...p }) => <a href={href} target={href?.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className="text-primary underline underline-offset-2" {...p} />,
          blockquote: (p) => <blockquote className="border-l-2 border-amber-500/50 pl-3 text-muted-foreground" {...p} />,
          code: (p) => <code className="rounded bg-muted px-1 py-0.5 text-xs font-mono" {...p} />,
          table: (p) => (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse my-2" {...p} />
            </div>
          ),
          th: (p) => <th className="border border-border/50 bg-muted/40 px-2 py-1.5 text-left font-semibold" {...p} />,
          td: (p) => <td className="border border-border/40 px-2 py-1.5 font-mono" {...p} />,
          hr: () => <hr className="border-border/40 my-3" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
