import { useState } from "react";
import { useAuth } from "../hooks/useAuth.js";
import { Loader2 } from "lucide-react";

export function LoginPage() {
  const { signInWithGoogle, signInWithGithub, signInWithEmail, signUpWithEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const fn = mode === "signin" ? signInWithEmail : signUpWithEmail;
      const { error } = await fn(email, password);
      if (error) setError(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-0 px-4">
      <div className="w-full max-w-[380px]">
        {/* Brand */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-extrabold tracking-tight mb-2">
            <span className="text-accent">d</span>istill
          </h1>
          <p className="text-text-muted text-sm">
            Your personal intelligence platform
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl bg-surface-1 border border-border-subtle p-6 sm:p-8 shadow-2xl shadow-black/40">
          {/* OAuth */}
          <div className="space-y-2.5">
            <button
              onClick={signInWithGoogle}
              className="w-full h-11 rounded-xl bg-white text-zinc-900 text-sm font-medium hover:bg-zinc-50 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5"
            >
              <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>

            <button
              onClick={signInWithGithub}
              className="w-full h-11 rounded-xl bg-surface-3 text-text-primary text-sm font-medium hover:bg-zinc-700 active:scale-[0.98] transition-all flex items-center justify-center gap-2.5 border border-border-subtle"
            >
              <svg viewBox="0 0 24 24" className="w-[18px] h-[18px] fill-current">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              Continue with GitHub
            </button>
          </div>

          {/* Divider */}
          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-border-subtle" />
            <span className="text-text-muted text-xs uppercase tracking-widest">or</span>
            <div className="h-px flex-1 bg-border-subtle" />
          </div>

          {/* Email form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-11 px-4 rounded-xl bg-surface-2 text-text-primary text-sm border border-border-subtle placeholder:text-text-muted focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-11 px-4 rounded-xl bg-surface-2 text-text-primary text-sm border border-border-subtle placeholder:text-text-muted focus:border-accent/50 focus:ring-1 focus:ring-accent/20 focus:outline-none transition-colors"
              required
              minLength={6}
            />
            {error && (
              <p className="text-danger text-sm px-1">{error}</p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full h-11 rounded-xl bg-accent text-surface-0 text-sm font-semibold hover:bg-accent-hover active:scale-[0.98] disabled:opacity-50 transition-all flex items-center justify-center gap-2"
            >
              {submitting && <Loader2 size={16} className="animate-spin" />}
              {mode === "signin" ? "Sign In" : "Create Account"}
            </button>
          </form>

          <p className="text-center mt-4">
            <button
              type="button"
              onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
              className="text-text-muted text-sm hover:text-accent transition-colors"
            >
              {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
