import { useState, useEffect } from "react";
import { apiFetch } from "../lib/api.js";
import { Link, Check, Loader2 } from "lucide-react";

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
    <div className="space-y-8">
      <h2 className="text-2xl font-bold">Share a URL</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
            required
            className="w-full p-3 rounded-lg bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 focus:border-purple-500 focus:outline-none"
          />
        </div>
        <div>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note (optional)"
            className="w-full p-3 rounded-lg bg-zinc-900 border border-zinc-700 text-white placeholder-zinc-500 focus:border-purple-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !url.trim()}
          className="px-6 py-3 rounded-lg bg-purple-600 text-white font-medium hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {submitting ? <Loader2 size={18} className="animate-spin" /> :
           success ? <Check size={18} /> :
           <Link size={18} />}
          {success ? "Shared!" : "Share"}
        </button>
      </form>

      {/* Recent shares */}
      {shares.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-4 text-zinc-300">Recent Shares</h3>
          <div className="space-y-2">
            {shares.map((s) => (
              <div key={s.id} className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sm text-purple-400 hover:text-purple-300 truncate block">
                    {s.title || s.url}
                  </a>
                  {s.note && <p className="text-xs text-zinc-500 mt-0.5">{s.note}</p>}
                </div>
                <div className="flex items-center gap-2 ml-3 shrink-0">
                  {s.processedAt ? (
                    <span className="text-xs text-green-400">Processed</span>
                  ) : (
                    <span className="text-xs text-zinc-500">Pending</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
