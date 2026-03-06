import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api.js";
import { Sparkles, Share2, Send, Users } from "lucide-react";

interface FeedItem {
  id: number;
  userId: string;
  displayName: string;
  avatarUrl: string | null;
  type: string;
  title: string;
  summary: string | null;
  url: string | null;
  imageUrl: string | null;
  createdAt: string;
}

export function FeedPage() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<FeedItem[]>("/feed")
      .then(setItems)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const typeIcon = (type: string) => {
    switch (type) {
      case "highlight": return <Sparkles size={13} className="text-warning" />;
      case "share": return <Share2 size={13} className="text-accent" />;
      case "draft_published": return <Send size={13} className="text-success" />;
      default: return null;
    }
  };

  const typeLabel = (type: string) => {
    switch (type) {
      case "highlight": return "highlighted";
      case "share": return "shared";
      default: return "published";
    }
  };

  if (loading) {
    return (
      <div className="py-16 text-center">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
        <span className="text-text-muted text-sm">Loading feed...</span>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-20">
        <div className="w-16 h-16 rounded-2xl bg-surface-2 flex items-center justify-center mx-auto mb-4">
          <Users size={28} className="text-text-muted" />
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-1.5">No feed activity yet</h2>
        <p className="text-text-muted text-sm max-w-xs mx-auto">
          Follow others to see their highlights and shares here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl font-bold tracking-tight text-text-primary mb-6">Feed</h2>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id} className="group p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle hover:border-border-default transition-colors">
            <div className="flex items-center gap-3 mb-3">
              {item.avatarUrl ? (
                <img src={item.avatarUrl} alt="" className="w-8 h-8 rounded-full" />
              ) : (
                <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-xs font-semibold text-accent">
                  {item.displayName[0]?.toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-text-primary">{item.displayName}</span>
                <div className="flex items-center gap-1.5 text-xs text-text-muted">
                  {typeIcon(item.type)}
                  <span>{typeLabel(item.type)}</span>
                  <span className="text-border-default">·</span>
                  <span>{new Date(item.createdAt).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
            <h4 className="font-medium text-text-primary leading-snug">
              {item.url ? (
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">
                  {item.title}
                </a>
              ) : item.title}
            </h4>
            {item.summary && <p className="text-sm text-text-secondary mt-1.5 leading-relaxed">{item.summary}</p>}
            {item.imageUrl && <img src={item.imageUrl} alt="" className="w-full h-40 object-cover rounded-lg mt-3" />}
          </div>
        ))}
      </div>
    </div>
  );
}
