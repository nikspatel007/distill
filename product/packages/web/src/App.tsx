import { useAuth } from "./hooks/useAuth.js";
import { useTheme } from "./hooks/useTheme.js";
import { LoginPage } from "./pages/Login.js";
import { DailyView } from "./pages/DailyView.js";
import { FeedPage } from "./pages/Feed.js";
import { SharePage } from "./pages/Share.js";
import { useState } from "react";
import { LayoutDashboard, Rss, Send, LogOut, Sun, Moon } from "lucide-react";

type Tab = "daily" | "feed" | "share";

export function App() {
  const { user, loading, signOut } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [tab, setTab] = useState<Tab>("daily");

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-0">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
          <span className="text-text-muted text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  const tabs = [
    { id: "daily" as const, label: "Today", icon: LayoutDashboard },
    { id: "feed" as const, label: "Feed", icon: Rss },
    { id: "share" as const, label: "Share", icon: Send },
  ];

  return (
    <div className="min-h-screen bg-surface-0">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-surface-0/80 backdrop-blur-xl border-b border-border-subtle">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <h1 className="text-lg font-bold tracking-tight text-text-primary">
              <span className="text-accent">d</span>istill
            </h1>
            <nav className="hidden sm:flex items-center">
              {tabs.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`relative px-3 py-1.5 text-sm font-medium rounded-lg transition-all duration-200 ${
                    tab === id
                      ? "text-text-primary bg-accent-dim"
                      : "text-text-muted hover:text-text-secondary"
                  }`}
                >
                  <Icon size={15} className="inline mr-1.5 -mt-px" />
                  {label}
                </button>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
              title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
            <div className="hidden sm:flex items-center gap-2 text-sm text-text-muted ml-1">
              <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center text-xs font-semibold text-accent">
                {user.email?.[0]?.toUpperCase()}
              </div>
              <span className="max-w-[160px] truncate">{user.email}</span>
            </div>
            <button
              onClick={signOut}
              className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>

        {/* Mobile tab bar */}
        <nav className="sm:hidden flex border-t border-border-subtle">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex-1 py-2.5 text-xs font-medium text-center transition-colors ${
                tab === id
                  ? "text-accent border-b-2 border-accent"
                  : "text-text-muted"
              }`}
            >
              <Icon size={16} className="mx-auto mb-0.5" />
              {label}
            </button>
          ))}
        </nav>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {tab === "daily" && <DailyView />}
        {tab === "feed" && <FeedPage />}
        {tab === "share" && <SharePage />}
      </main>
    </div>
  );
}
