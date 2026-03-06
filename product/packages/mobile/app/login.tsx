import { useState } from "react";
import { View, Text, TouchableOpacity, TextInput, StyleSheet, KeyboardAvoidingView, Platform } from "react-native";
import { useAuth } from "../lib/auth";
import { colors } from "../lib/colors";

export default function LoginScreen() {
  const { signInWithGoogle, signInWithGithub, signInWithEmail, signUpWithEmail } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
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
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
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

        <View style={styles.divider}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>or</Text>
          <View style={styles.dividerLine} />
        </View>

        <View style={styles.form}>
          <TextInput
            style={styles.input}
            placeholder="Email"
            placeholderTextColor={colors.text.muted}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TextInput
            style={styles.input}
            placeholder="Password"
            placeholderTextColor={colors.text.muted}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />
          {error && <Text style={styles.error}>{error}</Text>}
          <TouchableOpacity
            style={[styles.submitButton, submitting && styles.submitButtonDisabled]}
            onPress={handleSubmit}
            activeOpacity={0.8}
            disabled={submitting}
          >
            <Text style={styles.submitButtonText}>
              {mode === "signin" ? "Sign In" : "Create Account"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => setMode(mode === "signin" ? "signup" : "signin")}
          >
            <Text style={styles.switchText}>
              {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
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
  divider: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 24,
    gap: 12,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border.primary,
  },
  dividerText: {
    color: colors.text.muted,
    fontSize: 12,
  },
  form: {
    gap: 12,
  },
  input: {
    backgroundColor: colors.bg.tertiary,
    color: colors.text.primary,
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border.primary,
    fontSize: 16,
  },
  error: {
    color: "#f87171",
    fontSize: 14,
  },
  submitButton: {
    backgroundColor: colors.accent.purple,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitButtonText: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
  switchText: {
    color: colors.text.muted,
    fontSize: 14,
    textAlign: "center",
    marginTop: 4,
  },
});
