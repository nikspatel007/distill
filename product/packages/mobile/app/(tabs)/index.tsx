import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Linking,
  RefreshControl,
} from "react-native";
import { Sparkles, Link2, TrendingUp, Newspaper, Copy, Check } from "lucide-react-native";
import * as Clipboard from "expo-clipboard";
import { apiFetch } from "../../lib/api";
import { colors } from "../../lib/colors";
import type { ReadingBrief } from "@distill/shared";

export default function DailyViewScreen() {
  const [brief, setBrief] = useState<ReadingBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const loadBrief = useCallback(async () => {
    try {
      const data = await apiFetch<ReadingBrief>("/brief/latest");
      setBrief(data);
    } catch (err) {
      console.error("Failed to load brief:", err);
    }
  }, []);

  useEffect(() => {
    loadBrief().finally(() => setLoading(false));
  }, [loadBrief]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadBrief();
    setRefreshing(false);
  }, [loadBrief]);

  const copyToClipboard = async (text: string, platform: string) => {
    await Clipboard.setStringAsync(text);
    setCopied(platform);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.accent.purple} />
        <Text style={styles.loadingText}>Loading your brief...</Text>
      </View>
    );
  }

  if (!brief || brief.highlights.length === 0) {
    return (
      <View style={styles.centered}>
        <Newspaper size={48} color={colors.text.dimmed} />
        <Text style={styles.emptyTitle}>No brief yet</Text>
        <Text style={styles.emptySubtitle}>
          Share some URLs or wait for the daily pipeline to run.
        </Text>
      </View>
    );
  }

  const statusColors = (status: string) => {
    switch (status) {
      case "trending":
        return colors.status.trending;
      case "emerging":
        return colors.status.emerging;
      case "cooling":
        return colors.status.cooling;
      default:
        return colors.status.stable;
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent.purple}
        />
      }
    >
      {/* Date header */}
      <View style={styles.header}>
        <Text style={styles.dateText}>{brief.date}</Text>
        {brief.generatedAt ? (
          <Text style={styles.generatedText}>
            {new Date(brief.generatedAt).toLocaleTimeString()}
          </Text>
        ) : null}
      </View>

      {/* 3 Things Worth Knowing */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Sparkles size={20} color={colors.accent.amber} />
          <Text style={styles.sectionTitle}>3 Things Worth Knowing</Text>
        </View>
        {brief.highlights.map((h, i) => (
          <TouchableOpacity
            key={i}
            style={styles.card}
            onPress={() => {
              if (h.url) Linking.openURL(h.url);
            }}
            activeOpacity={h.url ? 0.7 : 1}
          >
            <Text style={styles.highlightTitle}>{h.title}</Text>
            <Text style={styles.highlightSource}>{h.source}</Text>
            <Text style={styles.highlightSummary}>{h.summary}</Text>
            {h.tags.length > 0 && (
              <View style={styles.tagsRow}>
                {h.tags.map((tag) => (
                  <View key={tag} style={styles.tag}>
                    <Text style={styles.tagText}>{tag}</Text>
                  </View>
                ))}
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* Connection */}
      {brief.connection && (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Link2 size={20} color={colors.accent.blue} />
            <Text style={styles.sectionTitle}>Connection</Text>
          </View>
          <View style={styles.card}>
            <Text style={styles.connectionText}>
              {brief.connection.explanation}
            </Text>
            <View style={styles.connectionBadgeRow}>
              <View style={styles.connectionBadge}>
                <Text style={styles.connectionBadgeText}>
                  {brief.connection.connectionType}
                </Text>
              </View>
            </View>
          </View>
        </View>
      )}

      {/* Ready to Post */}
      {brief.drafts.length > 0 && (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <TrendingUp size={20} color={colors.accent.green} />
            <Text style={styles.sectionTitle}>Ready to Post</Text>
          </View>
          {brief.drafts.map((draft, i) => (
            <View key={i} style={styles.card}>
              <View style={styles.draftHeader}>
                <Text style={styles.draftPlatform}>{draft.platform}</Text>
                <TouchableOpacity
                  onPress={() => copyToClipboard(draft.content, draft.platform)}
                  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                >
                  {copied === draft.platform ? (
                    <Check size={18} color={colors.accent.green} />
                  ) : (
                    <Copy size={18} color={colors.text.muted} />
                  )}
                </TouchableOpacity>
              </View>
              <Text style={styles.draftContent}>{draft.content}</Text>
              <Text style={styles.draftCharCount}>{draft.charCount} chars</Text>
            </View>
          ))}
        </View>
      )}

      {/* Learning Pulse */}
      {brief.learningPulse.length > 0 && (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <TrendingUp size={20} color={colors.accent.purple} />
            <Text style={styles.sectionTitle}>Learning Pulse</Text>
          </View>
          <View style={styles.pulseGrid}>
            {brief.learningPulse.map((t) => {
              const sc = statusColors(t.status);
              return (
                <View key={t.topic} style={styles.pulseCard}>
                  <Text style={styles.pulseTopic}>{t.topic}</Text>
                  <View
                    style={[styles.statusBadge, { backgroundColor: sc.bg }]}
                  >
                    <Text style={[styles.statusText, { color: sc.text }]}>
                      {t.status}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      )}
    </ScrollView>
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
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.bg.primary,
    padding: 24,
  },
  loadingText: {
    marginTop: 12,
    color: colors.text.muted,
    fontSize: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "600",
    color: colors.text.secondary,
    marginTop: 16,
    marginBottom: 8,
  },
  emptySubtitle: {
    color: colors.text.muted,
    textAlign: "center",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  dateText: {
    fontSize: 24,
    fontWeight: "700",
    color: colors.text.primary,
  },
  generatedText: {
    fontSize: 12,
    color: colors.text.muted,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: colors.text.primary,
  },
  card: {
    padding: 16,
    borderRadius: 16,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    marginBottom: 12,
  },
  highlightTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text.primary,
    marginBottom: 4,
  },
  highlightSource: {
    fontSize: 13,
    color: colors.text.tertiary,
    marginBottom: 8,
  },
  highlightSummary: {
    fontSize: 14,
    color: colors.text.secondary,
    lineHeight: 20,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 10,
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    backgroundColor: colors.bg.tertiary,
  },
  tagText: {
    fontSize: 12,
    color: colors.text.tertiary,
  },
  connectionText: {
    fontSize: 14,
    color: colors.text.secondary,
    lineHeight: 20,
  },
  connectionBadgeRow: {
    flexDirection: "row",
    marginTop: 10,
  },
  connectionBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: "rgba(59, 130, 246, 0.15)",
  },
  connectionBadgeText: {
    fontSize: 12,
    color: colors.accent.blue,
  },
  draftHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  draftPlatform: {
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    color: colors.text.muted,
  },
  draftContent: {
    fontSize: 14,
    color: colors.text.secondary,
    lineHeight: 20,
  },
  draftCharCount: {
    fontSize: 12,
    color: colors.text.dimmed,
    marginTop: 8,
  },
  pulseGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  pulseCard: {
    flexBasis: "47%",
    flexGrow: 1,
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  pulseTopic: {
    fontSize: 14,
    fontWeight: "500",
    color: colors.text.primary,
    flexShrink: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginLeft: 6,
  },
  statusText: {
    fontSize: 11,
  },
});
