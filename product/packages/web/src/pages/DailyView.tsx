import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import type { ReadingBrief } from "@distill/shared";
import { Sparkles, Link2, TrendingUp, Newspaper, Copy, Check } from "lucide-react";

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
    return <div className="animate-pulse text-zinc-500 py-12 text-center">Loading your brief...</div>;
  }

  if (!brief || brief.highlights.length === 0) {
    return (
      <div className="text-center py-16">
        <Newspaper size={48} className="mx-auto text-zinc-700 mb-4" />
        <h2 className="text-xl font-semibold text-zinc-300 mb-2">No brief yet</h2>
        <p className="text-zinc-500">Share some URLs or wait for the daily pipeline to run.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Date header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{brief.date}</h2>
        <span className="text-xs text-zinc-500">
          Generated {brief.generatedAt ? new Date(brief.generatedAt).toLocaleTimeString() : ""}
        </span>
      </div>

      {/* 3 Things Worth Knowing */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={20} className="text-amber-400" />
          <h3 className="text-lg font-semibold">3 Things Worth Knowing</h3>
        </div>
        <div className="space-y-4">
          {brief.highlights.map((h, i) => (
            <div key={i} className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
              {h.imageUrl && (
                <img src={h.imageUrl} alt="" className="w-full h-40 object-cover rounded-lg mb-3" />
              )}
              <h4 className="font-semibold text-white mb-1">
                <a href={h.url} target="_blank" rel="noopener noreferrer" className="hover:text-purple-400 transition-colors">
                  {h.title}
                </a>
              </h4>
              <p className="text-sm text-zinc-400 mb-2">{h.source}</p>
              <p className="text-sm text-zinc-300">{h.summary}</p>
              {h.tags.length > 0 && (
                <div className="flex gap-1.5 mt-2">
                  {h.tags.map((tag) => (
                    <span key={tag} className="px-2 py-0.5 text-xs rounded-full bg-zinc-800 text-zinc-400">
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
          <div className="flex items-center gap-2 mb-4">
            <Link2 size={20} className="text-blue-400" />
            <h3 className="text-lg font-semibold">Connection</h3>
          </div>
          <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
            <p className="text-sm text-zinc-300">{brief.connection.explanation}</p>
            <div className="flex items-center gap-2 mt-2 text-xs text-zinc-500">
              <span className="px-2 py-0.5 rounded-full bg-blue-900/30 text-blue-400">
                {brief.connection.connectionType}
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Ready to Post */}
      {brief.drafts.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={20} className="text-green-400" />
            <h3 className="text-lg font-semibold">Ready to Post</h3>
          </div>
          <div className="space-y-4">
            {brief.drafts.map((draft, i) => (
              <div key={i} className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                    {draft.platform}
                  </span>
                  <button
                    onClick={() => copyToClipboard(draft.content, draft.platform)}
                    className="text-zinc-500 hover:text-white transition-colors"
                  >
                    {copied === draft.platform ? <Check size={16} className="text-green-400" /> : <Copy size={16} />}
                  </button>
                </div>
                <p className="text-sm text-zinc-300 whitespace-pre-wrap">{draft.content}</p>
                <div className="mt-2 text-xs text-zinc-600">{draft.charCount} chars</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Learning Pulse */}
      {brief.learningPulse.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={20} className="text-purple-400" />
            <h3 className="text-lg font-semibold">Learning Pulse</h3>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {brief.learningPulse.map((t) => (
              <div key={t.topic} className="p-3 rounded-lg bg-zinc-900 border border-zinc-800">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{t.topic}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    t.status === "trending" ? "bg-green-900/30 text-green-400" :
                    t.status === "emerging" ? "bg-blue-900/30 text-blue-400" :
                    t.status === "cooling" ? "bg-amber-900/30 text-amber-400" :
                    "bg-zinc-800 text-zinc-500"
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
