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
      case "highlight": return <Sparkles size={14} className="text-amber-400" />;
      case "share": return <Share2 size={14} className="text-blue-400" />;
      case "draft_published": return <Send size={14} className="text-green-400" />;
      default: return null;
    }
  };

  if (loading) {
    return <div className="animate-pulse text-zinc-500 py-12 text-center">Loading feed...</div>;
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-16">
        <Users size={48} className="mx-auto text-zinc-700 mb-4" />
        <h2 className="text-xl font-semibold text-zinc-300 mb-2">No feed activity yet</h2>
        <p className="text-zinc-500">Follow others to see their highlights and shares here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold mb-6">Feed</h2>
      {items.map((item) => (
        <div key={item.id} className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="flex items-center gap-3 mb-2">
            {item.avatarUrl ? (
              <img src={item.avatarUrl} alt="" className="w-8 h-8 rounded-full" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-bold">
                {item.displayName[0]?.toUpperCase()}
              </div>
            )}
            <div className="flex-1">
              <span className="text-sm font-medium">{item.displayName}</span>
              <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                {typeIcon(item.type)}
                <span>{item.type === "highlight" ? "highlighted" : item.type === "share" ? "shared" : "published"}</span>
                <span>·</span>
                <span>{new Date(item.createdAt).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          <h4 className="font-medium text-white">
            {item.url ? (
              <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-purple-400 transition-colors">
                {item.title}
              </a>
            ) : item.title}
          </h4>
          {item.summary && <p className="text-sm text-zinc-400 mt-1">{item.summary}</p>}
          {item.imageUrl && <img src={item.imageUrl} alt="" className="w-full h-40 object-cover rounded-lg mt-3" />}
        </div>
      ))}
    </div>
  );
}
