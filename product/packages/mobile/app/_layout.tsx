import { Slot, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { View, StyleSheet } from "react-native";
import { ShareIntentProvider } from "expo-share-intent";
import { AuthProvider, useAuth } from "../lib/auth";
import { useIncomingShareIntent } from "../lib/useShareIntent";
import { colors } from "../lib/colors";

function ShareIntentHandler() {
  const { user } = useAuth();
  useIncomingShareIntent({ isAuthenticated: !!user });
  return null;
}

function RootLayoutNav() {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    const inAuthGroup = segments[0] === "login";

    if (!user && !inAuthGroup) {
      router.replace("/login");
    } else if (user && inAuthGroup) {
      router.replace("/");
    }
  }, [user, loading, segments]);

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      <ShareIntentHandler />
      <Slot />
    </View>
  );
}

export default function RootLayout() {
  return (
    <ShareIntentProvider>
      <AuthProvider>
        <RootLayoutNav />
      </AuthProvider>
    </ShareIntentProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg.primary,
  },
});
