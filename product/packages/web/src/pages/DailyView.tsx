import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import type { ReadingBrief } from "@distill/shared";
import { Sparkles, Link2, TrendingUp, Newspaper, Copy, Check, Send } from "lucide-react";

export function DailyView() {
  const [brief, setBrief] = useState<ReadingBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<ReadingBrief>("/brief/latest")
      .then(setBrief)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const copyToClipboard = (text: string, platform: string) => {
    navigator.clipboard.writeText(text);
    setCopied(platform);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <div className="py-16 text-center">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
        <span className="text-text-muted text-sm">Loading your brief...</span>
      </div>
    );
  }

  if (!brief || brief.highlights.length === 0) {
    return (
      <div className="text-center py-20">
        <div className="w-16 h-16 rounded-2xl bg-surface-2 flex items-center justify-center mx-auto mb-4">
          <Newspaper size={28} className="text-text-muted" />
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-1.5">No brief yet</h2>
        <p className="text-text-muted text-sm max-w-xs mx-auto">
          Share some URLs or wait for the daily pipeline to run.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Date header */}
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">{brief.date}</h2>
        <span className="text-xs text-text-muted">
          {brief.generatedAt ? new Date(brief.generatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : ""}
        </span>
      </div>

      {/* 3 Things Worth Knowing */}
      <section>
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-7 h-7 rounded-lg bg-warning/10 flex items-center justify-center">
            <Sparkles size={15} className="text-warning" />
          </div>
          <h3 className="text-base font-semibold text-text-primary">3 Things Worth Knowing</h3>
        </div>
        <div className="space-y-3">
          {brief.highlights.map((h, i) => (
            <div key={i} className="group p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle hover:border-border-default transition-colors">
              {h.imageUrl && (
                <img src={h.imageUrl} alt="" className="w-full h-40 object-cover rounded-lg mb-3" />
              )}
              <h4 className="font-semibold text-text-primary mb-1 leading-snug">
                <a
                  href={h.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-accent transition-colors"
                >
                  {h.title}
                </a>
              </h4>
              <p className="text-xs text-text-muted mb-2">{h.source}</p>
              <p className="text-sm text-text-secondary leading-relaxed">{h.summary}</p>
              {h.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {h.tags.map((tag) => (
                    <span key={tag} className="px-2 py-0.5 text-xs rounded-full bg-surface-2 text-text-muted border border-border-subtle">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Connection */}
      {brief.connection && (
        <section>
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center">
              <Link2 size={15} className="text-accent" />
            </div>
            <h3 className="text-base font-semibold text-text-primary">Connection</h3>
          </div>
          <div className="p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle">
            <p className="text-sm text-text-secondary leading-relaxed">{brief.connection.explanation}</p>
            <div className="mt-3">
              <span className="text-xs px-2.5 py-1 rounded-full bg-accent-dim text-accent font-medium">
                {brief.connection.connectionType}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Ready to Post */}
      {brief.drafts.length > 0 && (
        <section>
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-7 h-7 rounded-lg bg-success/10 flex items-center justify-center">
              <Send size={15} className="text-success" />
            </div>
            <h3 className="text-base font-semibold text-text-primary">Ready to Post</h3>
          </div>
          <div className="space-y-3">
            {brief.drafts.map((draft, i) => (
              <div key={i} className="p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                    {draft.platform}
                  </span>
                  <button
                    onClick={() => copyToClipboard(draft.content, draft.platform)}
                    className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
                    title="Copy to clipboard"
                  >
                    {copied === draft.platform ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                  </button>
                </div>
                <p className="text-sm text-text-secondary whitespace-pre-wrap leading-relaxed">{draft.content}</p>
                <div className="mt-3 flex items-center gap-2">
                  <div className="flex-1 h-1 rounded-full bg-surface-3 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        draft.charCount > 280 ? "bg-danger" : draft.charCount > 200 ? "bg-warning" : "bg-success"
                      }`}
                      style={{ width: `${Math.min(100, (draft.charCount / 280) * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-text-muted tabular-nums">{draft.charCount}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Learning Pulse */}
      {brief.learningPulse.length > 0 && (
        <section>
          <div className="flex items-center gap-2.5 mb-5">
            <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center">
              <TrendingUp size={15} className="text-accent" />
            </div>
            <h3 className="text-base font-semibold text-text-primary">Learning Pulse</h3>
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            {brief.learningPulse.map((t) => (
              <div key={t.topic} className="p-3.5 rounded-xl bg-surface-1 border border-border-subtle">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-text-primary truncate">{t.topic}</span>
                  <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0 ${
                    t.status === "trending" ? "bg-success/10 text-success" :
                    t.status === "emerging" ? "bg-accent-dim text-accent" :
                    t.status === "cooling" ? "bg-warning/10 text-warning" :
                    "bg-surface-2 text-text-muted"
                  }`}>
                    {t.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
