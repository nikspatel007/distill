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
import { Sparkles, Share2, Send, Users } from "lucide-react-native";
import { apiFetch } from "../../lib/api";
import { colors } from "../../lib/colors";
import type { FeedItem } from "@distill/shared";

export default function FeedScreen() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadFeed = useCallback(async () => {
    try {
      const data = await apiFetch<FeedItem[]>("/feed");
      setItems(data);
    } catch (err) {
      console.error("Failed to load feed:", err);
    }
  }, []);

  useEffect(() => {
    loadFeed().finally(() => setLoading(false));
  }, [loadFeed]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadFeed();
    setRefreshing(false);
  }, [loadFeed]);

  const typeIcon = (type: string) => {
    switch (type) {
      case "highlight":
        return <Sparkles size={14} color={colors.accent.amber} />;
      case "share":
        return <Share2 size={14} color={colors.accent.blue} />;
      case "draft_published":
        return <Send size={14} color={colors.accent.green} />;
      default:
        return null;
    }
  };

  const typeLabel = (type: string) => {
    switch (type) {
      case "highlight":
        return "highlighted";
      case "share":
        return "shared";
      case "draft_published":
        return "published";
      default:
        return type;
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.accent.purple} />
        <Text style={styles.loadingText}>Loading feed...</Text>
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.centered}>
        <Users size={48} color={colors.text.dimmed} />
        <Text style={styles.emptyTitle}>No feed activity yet</Text>
        <Text style={styles.emptySubtitle}>
          Follow others to see their highlights and shares here.
        </Text>
      </View>
    );
  }

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
      {items.map((item) => (
        <TouchableOpacity
          key={item.id}
          style={styles.card}
          onPress={() => {
            if (item.url) Linking.openURL(item.url);
          }}
          activeOpacity={item.url ? 0.7 : 1}
        >
          {/* Author row */}
          <View style={styles.authorRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>
                {(item.displayName[0] ?? "?").toUpperCase()}
              </Text>
            </View>
            <View style={styles.authorInfo}>
              <Text style={styles.authorName}>{item.displayName}</Text>
              <View style={styles.metaRow}>
                {typeIcon(item.type)}
                <Text style={styles.metaText}>{typeLabel(item.type)}</Text>
                <Text style={styles.metaDot}>{"\u00B7"}</Text>
                <Text style={styles.metaText}>
                  {new Date(item.createdAt).toLocaleDateString()}
                </Text>
              </View>
            </View>
          </View>

          {/* Content */}
          <Text style={styles.itemTitle}>{item.title}</Text>
          {item.summary && (
            <Text style={styles.itemSummary}>{item.summary}</Text>
          )}
        </TouchableOpacity>
      ))}
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
  card: {
    padding: 16,
    borderRadius: 16,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    marginBottom: 12,
  },
  authorRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 10,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.bg.tertiary,
    justifyContent: "center",
    alignItems: "center",
  },
  avatarText: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.text.secondary,
  },
  authorInfo: {
    flex: 1,
  },
  authorName: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text.primary,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 2,
  },
  metaText: {
    fontSize: 12,
    color: colors.text.muted,
  },
  metaDot: {
    fontSize: 12,
    color: colors.text.muted,
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text.primary,
  },
  itemSummary: {
    fontSize: 14,
    color: colors.text.tertiary,
    marginTop: 6,
    lineHeight: 20,
  },
});
