import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useAuth } from "../lib/auth";
import { colors } from "../lib/colors";

export default function LoginScreen() {
  const { signInWithGoogle, signInWithGithub } = useAuth();

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>Distill</Text>
        <Text style={styles.subtitle}>Your personal intelligence platform</Text>

        <View style={styles.buttons}>
          <TouchableOpacity
            style={styles.googleButton}
            onPress={signInWithGoogle}
            activeOpacity={0.8}
          >
            <Text style={styles.googleButtonText}>Continue with Google</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.githubButton}
            onPress={signInWithGithub}
            activeOpacity={0.8}
          >
            <Text style={styles.githubButtonText}>Continue with GitHub</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.bg.primary,
    padding: 24,
  },
  card: {
    width: "100%",
    maxWidth: 380,
    padding: 32,
    borderRadius: 20,
    backgroundColor: colors.bg.secondary,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  title: {
    fontSize: 32,
    fontWeight: "800",
    textAlign: "center",
    color: colors.accent.purple,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: colors.text.muted,
    textAlign: "center",
    marginBottom: 32,
  },
  buttons: {
    gap: 12,
  },
  googleButton: {
    backgroundColor: "#ffffff",
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 12,
    alignItems: "center",
  },
  googleButtonText: {
    color: "#1f2937",
    fontSize: 16,
    fontWeight: "600",
  },
  githubButton: {
    backgroundColor: colors.bg.tertiary,
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 12,
    alignItems: "center",
  },
  githubButtonText: {
    color: colors.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
});
