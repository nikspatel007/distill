import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api.js";
import { Link, Check, Loader2, ExternalLink } from "lucide-react";

interface SharedUrl {
  id: number;
  url: string;
  title: string | null;
  note: string | null;
  createdAt: string;
  processedAt: string | null;
}

export function SharePage() {
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [shares, setShares] = useState<SharedUrl[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const loadShares = () => {
    apiFetch<SharedUrl[]>("/share").then(setShares).catch(console.error);
  };

  useEffect(() => { loadShares(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    try {
      await apiFetch("/share", {
        method: "POST",
        body: JSON.stringify({ url: url.trim(), note: note.trim() || undefined }),
      });
      setUrl("");
      setNote("");
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
      loadShares();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-10">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary mb-1">Share a URL</h2>
        <p className="text-sm text-text-muted">Add articles, threads, or videos to your reading pipeline.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://..."
          required
          className="w-full h-12 px-4 rounded-xl bg-surface-1 text-text-primary text-sm border border-border-subtle placeholder:text-text-muted focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
        />
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add a note (optional)"
          className="w-full h-12 px-4 rounded-xl bg-surface-1 text-text-primary text-sm border border-border-subtle placeholder:text-text-muted focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
        />
        <button
          type="submit"
          disabled={submitting || !url.trim()}
          className="h-11 px-6 rounded-xl bg-accent text-white text-sm font-semibold hover:bg-accent-hover active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> :
           success ? <Check size={16} /> :
           <Link size={16} />}
          {success ? "Shared!" : "Share"}
        </button>
      </form>

      {/* Recent shares */}
      {shares.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">Recent Shares</h3>
          <div className="space-y-2">
            {shares.map((s) => (
              <div key={s.id} className="group p-3.5 rounded-xl bg-surface-1 border border-border-subtle hover:border-border-default transition-colors flex items-center justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-accent hover:text-accent-hover transition-colors truncate block font-medium"
                  >
                    {s.title || s.url}
                  </a>
                  {s.note && <p className="text-xs text-text-muted mt-0.5">{s.note}</p>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {s.processedAt ? (
                    <span className="text-xs text-success font-medium flex items-center gap-1">
                      <Check size={12} />
                      Processed
                    </span>
                  ) : (
                    <span className="text-xs text-text-muted">Pending</span>
                  )}
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1 rounded text-text-muted hover:text-text-primary opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <ExternalLink size={13} />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
