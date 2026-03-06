import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Linking,
  RefreshControl,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Link, Check, Loader2, Clipboard } from "lucide-react-native";
import * as ExpoClipboard from "expo-clipboard";
import { apiFetch } from "../../lib/api";
import { colors } from "../../lib/colors";
import { consumePendingShareUrl } from "../../lib/shareIntentState";
import type { SharedUrl } from "@distill/shared";

export default function ShareScreen() {
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [shares, setShares] = useState<SharedUrl[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [loadingShares, setLoadingShares] = useState(true);

  const loadShares = useCallback(async () => {
    try {
      const data = await apiFetch<SharedUrl[]>("/share");
      setShares(data);
    } catch (err) {
      console.error("Failed to load shares:", err);
    }
  }, []);

  useEffect(() => {
    loadShares().finally(() => setLoadingShares(false));
  }, [loadShares]);

  // Pick up any URL shared via the OS share sheet
  useEffect(() => {
    const pending = consumePendingShareUrl();
    if (pending) {
      setUrl(pending);
    }
  }, []);

  const handlePasteFromClipboard = async () => {
    const text = await ExpoClipboard.getStringAsync();
    if (text) {
      setUrl(text);
    }
  };

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setSubmitting(true);
    try {
      await apiFetch("/share", {
        method: "POST",
        body: JSON.stringify({ url: url.trim(), note: note.trim() || undefined }),
      });
      setUrl("");
      setNote("");
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
      await loadShares();
    } catch (err) {
      console.error("Failed to share:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={100}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={false}
            onRefresh={loadShares}
            tintColor={colors.accent.purple}
          />
        }
      >
        <Text style={styles.heading}>Share a URL</Text>

        {/* URL input */}
        <View style={styles.inputRow}>
          <TextInput
            style={styles.urlInput}
            value={url}
            onChangeText={setUrl}
            placeholder="https://..."
            placeholderTextColor={colors.text.muted}
            keyboardType="url"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity
            style={styles.pasteButton}
            onPress={handlePasteFromClipboard}
            activeOpacity={0.7}
          >
            <Clipboard size={20} color={colors.text.tertiary} />
          </TouchableOpacity>
        </View>

        {/* Note input */}
        <TextInput
          style={styles.noteInput}
          value={note}
          onChangeText={setNote}
          placeholder="Add a note (optional)"
          placeholderTextColor={colors.text.muted}
        />

        {/* Submit button */}
        <TouchableOpacity
          style={[
            styles.submitButton,
            (!url.trim() || submitting) && styles.submitButtonDisabled,
          ]}
          onPress={handleSubmit}
          disabled={submitting || !url.trim()}
          activeOpacity={0.8}
        >
          {submitting ? (
            <ActivityIndicator size="small" color={colors.text.primary} />
          ) : success ? (
            <Check size={20} color={colors.text.primary} />
          ) : (
            <Link size={20} color={colors.text.primary} />
          )}
          <Text style={styles.submitButtonText}>
            {success ? "Shared!" : "Share"}
          </Text>
        </TouchableOpacity>

        {/* Recent shares */}
        {loadingShares ? (
          <ActivityIndicator
            size="small"
            color={colors.accent.purple}
            style={styles.sharesLoader}
          />
        ) : shares.length > 0 ? (
          <View style={styles.recentSection}>
            <Text style={styles.recentHeading}>Recent Shares</Text>
            {shares.map((s) => (
              <TouchableOpacity
                key={s.id ?? s.url}
                style={styles.shareCard}
                onPress={() => Linking.openURL(s.url)}
                activeOpacity={0.7}
              >
                <View style={styles.shareContent}>
                  <Text style={styles.shareTitle} numberOfLines={1}>
                    {s.title ?? s.url}
                  </Text>
                  {s.note && (
                    <Text style={styles.shareNote} numberOfLines={1}>
                      {s.note}
                    </Text>
                  )}
                </View>
                <View style={styles.shareStatus}>
                  {s.processedAt ? (
                    <Text style={styles.processedText}>Processed</Text>
                  ) : (
                    <Text style={styles.pendingText}>Pending</Text>
                  )}
                </View>
              </TouchableOpacity>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg.primary,
  },
  content: {
    padding: 16,
    paddingBottom: 32,
  },
  heading: {
    fontSize: 24,
    fontWeight: "700",
    color: colors.text.primary,
    marginBottom: 20,
  },
  inputRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  urlInput: {
    flex: 1,
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.bg.secondary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
    color: colors.text.primary,
    fontSize: 16,
  },
  pasteButton: {
    width: 48,
    justifyContent: "center",
    alignItems: "center",
    borderRadius: 12,
    backgroundColor: colors.bg.secondary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
  },
  noteInput: {
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.bg.secondary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
    color: colors.text.primary,
    fontSize: 16,
    marginBottom: 16,
  },
  submitButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    backgroundColor: colors.accent.purple,
  },
  submitButtonDisabled: {
    opacity: 0.5,
  },
  submitButtonText: {
    color: colors.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
  sharesLoader: {
    marginTop: 32,
  },
  recentSection: {
    marginTop: 32,
  },
  recentHeading: {
    fontSize: 18,
    fontWeight: "600",
    color: colors.text.secondary,
    marginBottom: 12,
  },
  shareCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    marginBottom: 8,
  },
  shareContent: {
    flex: 1,
    marginRight: 12,
  },
  shareTitle: {
    fontSize: 14,
    color: colors.accent.purpleLight,
  },
  shareNote: {
    fontSize: 12,
    color: colors.text.muted,
    marginTop: 2,
  },
  shareStatus: {
    flexShrink: 0,
  },
  processedText: {
    fontSize: 12,
    color: colors.accent.green,
  },
  pendingText: {
    fontSize: 12,
    color: colors.text.muted,
  },
});
