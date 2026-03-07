import { useState, useEffect, useRef, useCallback } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { apiFetch } from "../lib/api.js";
import { supabase } from "../lib/supabase.js";
import type { StudioItem, StudioItemList, StudioImage } from "@distill/shared";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  PenLine,
  ArrowLeft,
  Trash2,
  Check,
  Loader2,
  ExternalLink,
  ImagePlus,
  Send,
  Ghost,
  MessageSquare,
  FileText,
  Upload,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------

const CONTENT_TYPES = ["journal", "weekly", "thematic", "digest", "seed"] as const;

const CONTENT_TYPE_COLORS: Record<string, string> = {
  journal: "bg-accent-dim text-accent",
  weekly: "bg-success/10 text-success",
  thematic: "bg-warning/10 text-warning",
  digest: "bg-surface-2 text-text-secondary",
  seed: "bg-danger/10 text-danger",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-surface-2 text-text-muted",
  ready: "bg-warning/10 text-warning",
  published: "bg-success/10 text-success",
};

const PLATFORM_TABS = ["source", "ghost", "x", "linkedin", "reddit"] as const;
type PlatformTab = (typeof PLATFORM_TABS)[number];

const MOODS = [
  "reflective",
  "energetic",
  "cautionary",
  "triumphant",
  "intimate",
  "technical",
  "playful",
  "somber",
] as const;

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// StudioPage (top-level router)
// ---------------------------------------------------------------------------

export function StudioPage() {
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  if (selectedSlug) {
    return <StudioDetail slug={selectedSlug} onBack={() => setSelectedSlug(null)} />;
  }
  return <StudioList onSelect={setSelectedSlug} />;
}

// ---------------------------------------------------------------------------
// StudioList
// ---------------------------------------------------------------------------

function StudioList({ onSelect }: { onSelect: (slug: string) => void }) {
  const [items, setItems] = useState<StudioItemList[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState<string>("journal");
  const [creating, setCreating] = useState(false);

  const loadItems = useCallback(() => {
    apiFetch<{ items: StudioItemList[] }>("/studio/items")
      .then((data) => setItems(data.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      const created = await apiFetch<StudioItem>("/studio/items", {
        method: "POST",
        body: JSON.stringify({ title: newTitle.trim(), contentType: newType }),
      });
      setNewTitle("");
      setNewType("journal");
      setShowNewForm(false);
      onSelect(created.slug);
    } catch (err) {
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const drafts = items.filter((i) => i.status !== "published");
  const published = items.filter((i) => i.status === "published");

  if (loading) {
    return (
      <div className="py-16 text-center">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
        <span className="text-text-muted text-sm">Loading studio...</span>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-text-primary">Content Studio</h2>
            <p className="text-sm text-text-muted mt-1">
              Create, refine, and publish across platforms.
            </p>
          </div>
          <button
            onClick={() => setShowNewForm(!showNewForm)}
            className="h-10 px-4 rounded-xl bg-accent text-white text-sm font-semibold hover:bg-accent-hover active:scale-[0.98] transition-all flex items-center gap-2"
          >
            <PenLine size={15} />
            New Post
          </button>
        </div>

        {/* New post form */}
        {showNewForm && (
          <form
            onSubmit={handleCreate}
            className="p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle space-y-3"
          >
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Post title..."
              required
              autoFocus
              className="w-full h-11 px-4 rounded-xl bg-surface-0 text-text-primary text-sm border border-border-subtle placeholder:text-text-muted focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
            />
            <div className="flex items-center gap-3">
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                className="h-10 px-3 rounded-xl bg-surface-0 text-text-primary text-sm border border-border-subtle focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
              >
                {CONTENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-2 ml-auto">
                <button
                  type="button"
                  onClick={() => setShowNewForm(false)}
                  className="h-10 px-4 rounded-xl text-sm text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newTitle.trim()}
                  className="h-10 px-5 rounded-xl bg-accent text-white text-sm font-semibold hover:bg-accent-hover active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
                >
                  {creating && <Loader2 size={14} className="animate-spin" />}
                  Create
                </button>
              </div>
            </div>
          </form>
        )}

        {/* Empty state */}
        {items.length === 0 && !showNewForm && (
          <div className="text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-surface-2 flex items-center justify-center mx-auto mb-4">
              <PenLine size={28} className="text-text-muted" />
            </div>
            <h3 className="text-lg font-semibold text-text-primary mb-1.5">No posts yet</h3>
            <p className="text-text-muted text-sm max-w-xs mx-auto">
              Create your first post to start writing and publishing.
            </p>
          </div>
        )}

        {/* Drafts section */}
        {drafts.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
              Drafts
            </h3>
            <div className="space-y-2">
              {drafts.map((item) => (
                <StudioListCard key={item.id} item={item} onClick={() => onSelect(item.slug)} />
              ))}
            </div>
          </div>
        )}

        {/* Published section */}
        {published.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
              Published
            </h3>
            <div className="space-y-2">
              {published.map((item) => (
                <StudioListCard key={item.id} item={item} onClick={() => onSelect(item.slug)} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StudioListCard
// ---------------------------------------------------------------------------

function StudioListCard({ item, onClick }: { item: StudioItemList; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left group p-4 sm:p-5 rounded-xl bg-surface-1 border border-border-subtle hover:border-border-default transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className="font-semibold text-text-primary leading-snug group-hover:text-accent transition-colors truncate">
            {item.title}
          </h4>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <span
              className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${CONTENT_TYPE_COLORS[item.contentType] ?? "bg-surface-2 text-text-muted"}`}
            >
              {item.contentType}
            </span>
            <span
              className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[item.status] ?? "bg-surface-2 text-text-muted"}`}
            >
              {item.status}
            </span>
            <span className="text-xs text-text-muted">{timeAgo(item.updatedAt)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 mt-1">
          {item.platformsPublished > 0 && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-success/10 text-success font-medium flex items-center gap-1">
              <Check size={10} />
              {item.platformsPublished}
            </span>
          )}
          {item.platformsReady > 0 && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-surface-2 text-text-muted font-medium">
              {item.platformsReady} ready
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// StudioDetail
// ---------------------------------------------------------------------------

interface GhostTarget {
  id: string;
  name: string;
  url: string;
}

interface PostizIntegration {
  id: string;
  name: string;
  platform: string;
  connected: boolean;
}

function StudioDetail({ slug, onBack }: { slug: string; onBack: () => void }) {
  const [item, setItem] = useState<StudioItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  // Platform content tab
  const [platformTab, setPlatformTab] = useState<PlatformTab>("source");

  // Mobile tab
  const [mobileTab, setMobileTab] = useState<"content" | "publish" | "chat">("content");

  // Ghost targets
  const [ghostTargets, setGhostTargets] = useState<GhostTarget[]>([]);
  const [ghostStatuses, setGhostStatuses] = useState<Record<string, string>>({});
  const [ghostPublishing, setGhostPublishing] = useState<Record<string, boolean>>({});

  // Postiz integrations
  const [postizIntegrations, setPostizIntegrations] = useState<PostizIntegration[]>([]);
  const [postizModes, setPostizModes] = useState<Record<string, string>>({});
  const [postizPublishing, setPostizPublishing] = useState<Record<string, boolean>>({});

  // Images
  const [images, setImages] = useState<StudioImage[]>([]);
  const [imageMood, setImageMood] = useState<string>("reflective");
  const [generatingImages, setGeneratingImages] = useState(false);

  const loadItem = useCallback(() => {
    apiFetch<StudioItem & { images: StudioImage[] }>(`/studio/items/${slug}`)
      .then((data) => {
        setItem(data);
        setImages(data.images ?? []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    loadItem();
    apiFetch<{ targets: GhostTarget[] }>("/studio/ghost/targets")
      .then((data) => setGhostTargets(data.targets))
      .catch(console.error);
    apiFetch<{ integrations: PostizIntegration[]; configured: boolean }>("/studio/platforms")
      .then((data) => setPostizIntegrations(data.integrations))
      .catch(console.error);
  }, [loadItem]);

  const handleDelete = async () => {
    if (!confirm("Delete this post? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await apiFetch(`/studio/items/${slug}`, { method: "DELETE" });
      onBack();
    } catch (err) {
      console.error(err);
      setDeleting(false);
    }
  };

  const handleGhostPublish = async (targetId: string) => {
    setGhostPublishing((p) => ({ ...p, [targetId]: true }));
    try {
      await apiFetch(`/studio/ghost/publish/${slug}`, {
        method: "POST",
        body: JSON.stringify({
          target: targetId,
          status: ghostStatuses[targetId] ?? "draft",
          tags: item?.tags ?? [],
        }),
      });
      loadItem();
    } catch (err) {
      console.error(err);
    } finally {
      setGhostPublishing((p) => ({ ...p, [targetId]: false }));
    }
  };

  const handlePostizPublish = async (integrationId: string) => {
    setPostizPublishing((p) => ({ ...p, [integrationId]: true }));
    try {
      await apiFetch(`/studio/publish/${slug}`, {
        method: "POST",
        body: JSON.stringify({
          platforms: [integrationId],
          mode: postizModes[integrationId] ?? "draft",
        }),
      });
      loadItem();
    } catch (err) {
      console.error(err);
    } finally {
      setPostizPublishing((p) => ({ ...p, [integrationId]: false }));
    }
  };

  const handleGenerateImages = async () => {
    setGeneratingImages(true);
    try {
      await apiFetch(`/studio/items/${slug}/images/batch`, {
        method: "POST",
        body: JSON.stringify({ mood: imageMood }),
      });
      loadItem();
    } catch (err) {
      console.error(err);
    } finally {
      setGeneratingImages(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 text-center">
        <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-3" />
        <span className="text-text-muted text-sm">Loading post...</span>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 text-center">
        <p className="text-text-muted">Post not found.</p>
        <button
          onClick={onBack}
          className="mt-4 text-sm text-accent hover:text-accent-hover transition-colors"
        >
          Go back
        </button>
      </div>
    );
  }

  const contentPanel = (
    <ContentPanel
      item={item}
      platformTab={platformTab}
      setPlatformTab={setPlatformTab}
    />
  );

  const publishPanel = (
    <PublishPanel
      item={item}
      ghostTargets={ghostTargets}
      ghostStatuses={ghostStatuses}
      setGhostStatuses={setGhostStatuses}
      ghostPublishing={ghostPublishing}
      onGhostPublish={handleGhostPublish}
      postizIntegrations={postizIntegrations}
      postizModes={postizModes}
      setPostizModes={setPostizModes}
      postizPublishing={postizPublishing}
      onPostizPublish={handlePostizPublish}
      images={images}
      imageMood={imageMood}
      setImageMood={setImageMood}
      generatingImages={generatingImages}
      onGenerateImages={handleGenerateImages}
    />
  );

  const chatPanel = (
    <ChatPanel item={item} onItemUpdated={loadItem} />
  );

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      {/* Detail header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onBack}
            className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors shrink-0"
            title="Back to list"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="min-w-0">
            <h2 className="text-xl font-bold tracking-tight text-text-primary truncate">
              {item.title}
            </h2>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${CONTENT_TYPE_COLORS[item.contentType] ?? "bg-surface-2 text-text-muted"}`}
              >
                {item.contentType}
              </span>
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[item.status] ?? "bg-surface-2 text-text-muted"}`}
              >
                {item.status}
              </span>
              <span className="text-xs text-text-muted">{timeAgo(item.updatedAt)}</span>
            </div>
          </div>
        </div>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger/10 transition-colors shrink-0"
          title="Delete post"
        >
          {deleting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
        </button>
      </div>

      {/* Mobile tabs */}
      <div className="md:hidden flex border-b border-border-subtle mb-4">
        {(["content", "publish", "chat"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setMobileTab(t)}
            className={`flex-1 py-2.5 text-xs font-medium text-center transition-colors ${
              mobileTab === t
                ? "text-accent border-b-2 border-accent"
                : "text-text-muted"
            }`}
          >
            {t === "content" && <FileText size={14} className="mx-auto mb-0.5" />}
            {t === "publish" && <Upload size={14} className="mx-auto mb-0.5" />}
            {t === "chat" && <MessageSquare size={14} className="mx-auto mb-0.5" />}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Mobile content */}
      <div className="md:hidden">
        {mobileTab === "content" && contentPanel}
        {mobileTab === "publish" && (
          <div className="space-y-6">
            {publishPanel}
          </div>
        )}
        {mobileTab === "chat" && (
          <div className="h-[calc(100vh-220px)]">
            {chatPanel}
          </div>
        )}
      </div>

      {/* Desktop two-column */}
      <div className="hidden md:grid md:grid-cols-5 gap-6">
        <div className="col-span-3">{contentPanel}</div>
        <div className="col-span-2 space-y-6 flex flex-col" style={{ maxHeight: "calc(100vh - 180px)" }}>
          <div className="shrink-0">{publishPanel}</div>
          <div className="flex-1 min-h-0">{chatPanel}</div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ContentPanel — renders source markdown or platform-adapted content
// ---------------------------------------------------------------------------

function ContentPanel({
  item,
  platformTab,
  setPlatformTab,
}: {
  item: StudioItem;
  platformTab: PlatformTab;
  setPlatformTab: (tab: PlatformTab) => void;
}) {
  const getPlatformContent = (platform: string): string | null => {
    if (!item.platformContents) return null;
    const entry = item.platformContents[platform];
    return entry?.content ?? null;
  };

  return (
    <div>
      {/* Platform tab bar */}
      <div className="flex items-center gap-1 mb-4 overflow-x-auto pb-1">
        {PLATFORM_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setPlatformTab(tab)}
            className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all whitespace-nowrap ${
              platformTab === tab
                ? "text-text-primary bg-accent-dim"
                : "text-text-muted hover:text-text-secondary hover:bg-surface-2"
            }`}
          >
            {tab === "source" ? "Source" : tab === "ghost" ? "Ghost" : tab.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div className="rounded-xl bg-surface-1 border border-border-subtle p-4 sm:p-5 min-h-[300px]">
        {platformTab === "source" ? (
          item.content ? (
            <div className="prose prose-sm max-w-none text-text-secondary prose-headings:text-text-primary prose-a:text-accent prose-strong:text-text-primary prose-code:text-accent prose-code:bg-surface-2 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-surface-2 prose-pre:border prose-pre:border-border-subtle">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.content}</ReactMarkdown>
            </div>
          ) : (
            <EmptyPlatformContent message="No source content yet. Use the chat to start writing." />
          )
        ) : (
          <PlatformPreview
            platform={platformTab}
            content={getPlatformContent(platformTab)}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PlatformPreview — shows adapted content with platform-specific styling
// ---------------------------------------------------------------------------

function PlatformPreview({
  platform,
  content,
}: {
  platform: string;
  content: string | null;
}) {
  if (!content) {
    return <EmptyPlatformContent message="No content yet — use the chat to generate it." />;
  }

  if (platform === "x") {
    return <TwitterPreview content={content} />;
  }

  if (platform === "linkedin") {
    return <LinkedInPreview content={content} />;
  }

  if (platform === "ghost") {
    return (
      <div className="prose prose-sm max-w-none text-text-secondary prose-headings:text-text-primary prose-a:text-accent prose-strong:text-text-primary prose-code:text-accent prose-code:bg-surface-2 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-surface-2 prose-pre:border prose-pre:border-border-subtle">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }

  if (platform === "reddit") {
    return <RedditPreview content={content} />;
  }

  return <pre className="text-sm text-text-secondary whitespace-pre-wrap">{content}</pre>;
}

function TwitterPreview({ content }: { content: string }) {
  const tweets = content.split("---").map((t) => t.trim()).filter(Boolean);

  return (
    <div className="space-y-3">
      {tweets.map((tweet, i) => {
        const charCount = tweet.length;
        const overLimit = charCount > 280;
        return (
          <div key={i} className="p-3 rounded-lg bg-surface-0 border border-border-subtle">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] text-text-muted font-medium">
                Tweet {i + 1}/{tweets.length}
              </span>
              <span className={`text-[11px] font-medium tabular-nums ${overLimit ? "text-danger" : "text-text-muted"}`}>
                {charCount}/280
              </span>
            </div>
            <p className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">
              {tweet}
            </p>
            <div className="mt-2 h-1 rounded-full bg-surface-3 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  overLimit ? "bg-danger" : charCount > 240 ? "bg-warning" : "bg-success"
                }`}
                style={{ width: `${Math.min(100, (charCount / 280) * 100)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LinkedInPreview({ content }: { content: string }) {
  const charCount = content.length;
  const overLimit = charCount > 3000;

  return (
    <div>
      <p className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed">{content}</p>
      <div className="mt-4 flex items-center gap-2">
        <div className="flex-1 h-1 rounded-full bg-surface-3 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              overLimit ? "bg-danger" : charCount > 2500 ? "bg-warning" : "bg-success"
            }`}
            style={{ width: `${Math.min(100, (charCount / 3000) * 100)}%` }}
          />
        </div>
        <span className={`text-xs tabular-nums ${overLimit ? "text-danger" : "text-text-muted"}`}>
          {charCount.toLocaleString()}/3,000
        </span>
      </div>
    </div>
  );
}

function RedditPreview({ content }: { content: string }) {
  const lines = content.split("\n");
  const title = lines[0] ?? "";
  const body = lines.slice(1).join("\n").trim();

  return (
    <div>
      <div className="mb-3 pb-3 border-b border-border-subtle">
        <span className="text-[11px] text-text-muted font-medium uppercase tracking-wider">
          Title
        </span>
        <h4 className="text-sm font-semibold text-text-primary mt-1">{title}</h4>
      </div>
      {body && (
        <div className="prose prose-sm max-w-none text-text-secondary prose-headings:text-text-primary prose-a:text-accent prose-strong:text-text-primary">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

function EmptyPlatformContent({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-surface-2 flex items-center justify-center mb-3">
        <FileText size={20} className="text-text-muted" />
      </div>
      <p className="text-sm text-text-muted max-w-xs">{message}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PublishPanel — Ghost targets, Postiz integrations, images
// ---------------------------------------------------------------------------

function PublishPanel({
  item,
  ghostTargets,
  ghostStatuses,
  setGhostStatuses,
  ghostPublishing,
  onGhostPublish,
  postizIntegrations,
  postizModes,
  setPostizModes,
  postizPublishing,
  onPostizPublish,
  images,
  imageMood,
  setImageMood,
  generatingImages,
  onGenerateImages,
}: {
  item: StudioItem;
  ghostTargets: GhostTarget[];
  ghostStatuses: Record<string, string>;
  setGhostStatuses: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  ghostPublishing: Record<string, boolean>;
  onGhostPublish: (targetId: string) => void;
  postizIntegrations: PostizIntegration[];
  postizModes: Record<string, string>;
  setPostizModes: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  postizPublishing: Record<string, boolean>;
  onPostizPublish: (integrationId: string) => void;
  images: StudioImage[];
  imageMood: string;
  setImageMood: (mood: string) => void;
  generatingImages: boolean;
  onGenerateImages: () => void;
}) {
  const getPlatformStatus = (platform: string): { published: boolean; publishedAt: string | null } => {
    if (!item.platformContents) return { published: false, publishedAt: null };
    const entry = item.platformContents[platform];
    return {
      published: entry?.published ?? false,
      publishedAt: entry?.publishedAt ?? null,
    };
  };

  return (
    <div className="space-y-4">
      {/* Ghost targets */}
      {ghostTargets.length > 0 && (
        <div className="rounded-xl bg-surface-1 border border-border-subtle p-4">
          <div className="flex items-center gap-2 mb-3">
            <Ghost size={14} className="text-text-muted" />
            <h4 className="text-sm font-semibold text-text-primary">Ghost</h4>
          </div>
          <div className="space-y-2">
            {ghostTargets.map((target) => {
              const status = getPlatformStatus("ghost");
              return (
                <div key={target.id} className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text-primary truncate">{target.name}</p>
                    {status.published && (
                      <span className="text-[11px] text-success flex items-center gap-1 mt-0.5">
                        <Check size={10} /> Published
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <select
                      value={ghostStatuses[target.id] ?? "draft"}
                      onChange={(e) =>
                        setGhostStatuses((s) => ({ ...s, [target.id]: e.target.value }))
                      }
                      className="h-8 px-2 rounded-lg bg-surface-0 text-text-secondary text-xs border border-border-subtle focus:outline-none"
                    >
                      <option value="draft">Draft</option>
                      <option value="published">Published</option>
                    </select>
                    <button
                      onClick={() => onGhostPublish(target.id)}
                      disabled={ghostPublishing[target.id]}
                      className="h-8 px-3 rounded-lg bg-accent text-white text-xs font-semibold hover:bg-accent-hover disabled:opacity-50 transition-all flex items-center gap-1.5"
                    >
                      {ghostPublishing[target.id] ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Send size={11} />
                      )}
                      Publish
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Postiz integrations */}
      {postizIntegrations.length > 0 && (
        <div className="rounded-xl bg-surface-1 border border-border-subtle p-4">
          <div className="flex items-center gap-2 mb-3">
            <ExternalLink size={14} className="text-text-muted" />
            <h4 className="text-sm font-semibold text-text-primary">Postiz</h4>
          </div>
          <div className="space-y-2">
            {postizIntegrations.map((integration) => {
              const status = getPlatformStatus(integration.platform);
              return (
                <div key={integration.id} className="flex items-center justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text-primary truncate">
                      {integration.name}
                      <span className="text-text-muted ml-1.5 text-xs">
                        ({integration.platform})
                      </span>
                    </p>
                    {status.published && (
                      <span className="text-[11px] text-success flex items-center gap-1 mt-0.5">
                        <Check size={10} /> Published
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <select
                      value={postizModes[integration.id] ?? "draft"}
                      onChange={(e) =>
                        setPostizModes((m) => ({ ...m, [integration.id]: e.target.value }))
                      }
                      className="h-8 px-2 rounded-lg bg-surface-0 text-text-secondary text-xs border border-border-subtle focus:outline-none"
                    >
                      <option value="draft">Draft</option>
                      <option value="now">Publish Now</option>
                    </select>
                    <button
                      onClick={() => onPostizPublish(integration.id)}
                      disabled={postizPublishing[integration.id] || !integration.connected}
                      className="h-8 px-3 rounded-lg bg-accent text-white text-xs font-semibold hover:bg-accent-hover disabled:opacity-50 transition-all flex items-center gap-1.5"
                    >
                      {postizPublishing[integration.id] ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Send size={11} />
                      )}
                      Publish
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Images */}
      <div className="rounded-xl bg-surface-1 border border-border-subtle p-4">
        <div className="flex items-center gap-2 mb-3">
          <ImagePlus size={14} className="text-text-muted" />
          <h4 className="text-sm font-semibold text-text-primary">Images</h4>
        </div>

        {images.length > 0 && (
          <div className="grid grid-cols-2 gap-2 mb-3">
            {images.map((img) => (
              <div key={img.id} className="relative group rounded-lg overflow-hidden">
                <img
                  src={img.url}
                  alt={img.prompt}
                  className="w-full h-24 object-cover"
                />
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <span className="text-[10px] text-white px-2 py-1 rounded bg-black/60 max-w-full truncate">
                    {img.role}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2">
          <select
            value={imageMood}
            onChange={(e) => setImageMood(e.target.value)}
            className="h-8 flex-1 px-2 rounded-lg bg-surface-0 text-text-secondary text-xs border border-border-subtle focus:outline-none"
          >
            {MOODS.map((m) => (
              <option key={m} value={m}>
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </option>
            ))}
          </select>
          <button
            onClick={onGenerateImages}
            disabled={generatingImages}
            className="h-8 px-3 rounded-lg bg-accent text-white text-xs font-semibold hover:bg-accent-hover disabled:opacity-50 transition-all flex items-center gap-1.5"
          >
            {generatingImages ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <ImagePlus size={12} />
            )}
            Generate
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatPanel — AI chat using @ai-sdk/react useChat
// ---------------------------------------------------------------------------

/** Extract text content from a UIMessage's parts array. */
function getMessageText(msg: UIMessage): string {
  return msg.parts
    .filter((p): p is { type: "text"; text: string } => p.type === "text")
    .map((p) => p.text)
    .join("");
}

function ChatPanel({
  item,
  onItemUpdated,
}: {
  item: StudioItem;
  onItemUpdated: () => void;
}) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [inputValue, setInputValue] = useState("");

  const transport = new DefaultChatTransport({
    api: "/api/studio/chat",
    headers: async () => {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      return {
        Authorization: `Bearer ${token ?? ""}`,
      };
    },
    body: {
      content: item.content ?? "",
      platform: "source",
      slug: item.slug,
    },
  });

  const { messages, status, sendMessage } = useChat({
    transport,
    messages: (item.chatHistory ?? []).map((msg, i) => ({
      id: `history-${i}`,
      role: msg.role as "user" | "assistant",
      parts: [{ type: "text" as const, text: msg.content }],
    })),
    onFinish: () => {
      onItemUpdated();
    },
  });

  const isLoading = status === "submitted" || status === "streaming";

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const suggestions = [
    "Adapt for LinkedIn",
    "Make it shorter",
    "Add a hook",
    "Make it more technical",
    "Adapt for X (thread)",
  ];

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text || isLoading) return;
    setInputValue("");
    sendMessage({ text });
  };

  const handleSuggestionClick = (suggestion: string) => {
    if (isLoading) return;
    sendMessage({ text: suggestion });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="rounded-xl bg-surface-1 border border-border-subtle flex flex-col h-full min-h-[400px]">
      {/* Chat header */}
      <div className="px-4 py-3 border-b border-border-subtle shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="text-accent" />
          <h4 className="text-sm font-semibold text-text-primary">AI Assistant</h4>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-10 h-10 rounded-xl bg-accent-dim flex items-center justify-center mb-2">
              <MessageSquare size={18} className="text-accent" />
            </div>
            <p className="text-sm text-text-muted max-w-[200px]">
              Ask me to help write, adapt, or improve your content.
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-accent text-white rounded-br-sm"
                  : "bg-surface-2 text-text-primary rounded-bl-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none text-text-primary prose-headings:text-text-primary prose-a:text-accent prose-strong:text-text-primary prose-p:my-1 prose-ul:my-1 prose-li:my-0.5">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{getMessageText(msg)}</ReactMarkdown>
                </div>
              ) : (
                <span className="whitespace-pre-wrap">{getMessageText(msg)}</span>
              )}
            </div>
          </div>
        ))}
        {isLoading && messages[messages.length - 1]?.role === "user" && (
          <div className="flex justify-start">
            <div className="bg-surface-2 rounded-xl rounded-bl-sm px-3.5 py-2.5">
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-text-muted animate-pulse" />
                <div className="w-1.5 h-1.5 rounded-full bg-text-muted animate-pulse delay-100" style={{ animationDelay: "0.15s" }} />
                <div className="w-1.5 h-1.5 rounded-full bg-text-muted animate-pulse delay-200" style={{ animationDelay: "0.3s" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggestions */}
      {messages.length === 0 && (
        <div className="px-4 pb-2 shrink-0">
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => handleSuggestionClick(s)}
                disabled={isLoading}
                className="px-2.5 py-1 text-xs rounded-full bg-surface-2 text-text-secondary hover:bg-accent-dim hover:text-accent transition-colors disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="px-4 py-3 border-t border-border-subtle shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask the AI to help..."
            rows={1}
            className="flex-1 resize-none min-h-[40px] max-h-[120px] px-3 py-2.5 rounded-xl bg-surface-0 text-text-primary text-sm border border-border-subtle placeholder:text-text-muted focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
            style={{ fieldSizing: "content" } as React.CSSProperties}
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            className="h-10 w-10 shrink-0 rounded-xl bg-accent text-white flex items-center justify-center hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-[0.95]"
          >
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
