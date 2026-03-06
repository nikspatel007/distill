import { useAuth } from "./hooks/useAuth.js";
import { LoginPage } from "./pages/Login.js";
import { DailyView } from "./pages/DailyView.js";
import { FeedPage } from "./pages/Feed.js";
import { SharePage } from "./pages/Share.js";
import { useState } from "react";
import { LayoutDashboard, Users, Share2, LogOut } from "lucide-react";

type Tab = "daily" | "feed" | "share" | "settings";

export function App() {
  const { user, loading, signOut } = useAuth();
  const [tab, setTab] = useState<Tab>("daily");

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-white">
        <div className="animate-pulse text-lg">Loading...</div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Top nav */}
      <header className="border-b border-zinc-800 px-6 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
          Distill
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-zinc-400">{user.email}</span>
          <button onClick={signOut} className="text-zinc-500 hover:text-white transition-colors">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {/* Tab bar */}
      <nav className="border-b border-zinc-800 px-6 flex gap-1">
        {[
          { id: "daily" as const, label: "Daily View", icon: LayoutDashboard },
          { id: "feed" as const, label: "Feed", icon: Users },
          { id: "share" as const, label: "Share", icon: Share2 },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-purple-500 text-white"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Icon size={16} className="inline mr-2" />
            {label}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="max-w-4xl mx-auto p-6">
        {tab === "daily" && <DailyView />}
        {tab === "feed" && <FeedPage />}
        {tab === "share" && <SharePage />}
      </main>
    </div>
  );
}
