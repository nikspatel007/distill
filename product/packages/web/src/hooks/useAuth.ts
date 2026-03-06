import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase.js";
import type { User } from "@supabase/supabase-js";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const signInWithGoogle = () =>
    supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });

  const signInWithGithub = () =>
    supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo: window.location.origin },
    });

  const signInWithEmail = (email: string, password: string) =>
    supabase.auth.signInWithPassword({ email, password });

  const signUpWithEmail = (email: string, password: string) =>
    supabase.auth.signUp({ email, password });

  const signOut = () => supabase.auth.signOut();

  return { user, loading, signInWithGoogle, signInWithGithub, signInWithEmail, signUpWithEmail, signOut };
}
