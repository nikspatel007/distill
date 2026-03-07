import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  Alert,
} from "react-native";
import { PenLine, Plus, X } from "lucide-react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { apiFetch } from "../../lib/api";
import { colors } from "../../lib/colors";
import type { StudioItemList, CreateStudioItem } from "@distill/shared";

const CONTENT_TYPES = ["journal", "weekly", "thematic", "digest", "seed"] as const;

type ContentType = (typeof CONTENT_TYPES)[number];

const contentTypeColors: Record<ContentType, string> = {
  journal: colors.accent.purple,
  weekly: colors.accent.blue,
  thematic: colors.accent.amber,
  digest: colors.accent.green,
  seed: colors.accent.red,
};

const statusColors: Record<string, { bg: string; text: string }> = {
  draft: { bg: "rgba(107, 114, 128, 0.15)", text: colors.text.muted },
  ready: { bg: "rgba(96, 165, 250, 0.15)", text: colors.accent.blue },
  published: { bg: "rgba(74, 222, 128, 0.15)", text: colors.accent.green },
};

export default function StudioScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<StudioItemList[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContentType, setNewContentType] = useState<ContentType>("journal");
  const [creating, setCreating] = useState(false);

  const loadItems = useCallback(async () => {
    try {
      const data = await apiFetch<{ items: StudioItemList[] }>("/studio/items");
      setItems(data.items);
    } catch (err) {
      console.error("Failed to load studio items:", err);
    }
  }, []);

  useEffect(() => {
    loadItems().finally(() => setLoading(false));
  }, [loadItems]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadItems();
    setRefreshing(false);
  }, [loadItems]);

  const handleCreate = async () => {
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      const body: CreateStudioItem = {
        title: newTitle.trim(),
        contentType: newContentType,
      };
      const created = await apiFetch<{ slug: string }>("/studio/items", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setModalVisible(false);
      setNewTitle("");
      setNewContentType("journal");
      router.push(`/studio/${created.slug}`);
    } catch (err) {
      Alert.alert("Error", "Failed to create item. Please try again.");
      console.error("Failed to create studio item:", err);
    } finally {
      setCreating(false);
    }
  };

  const drafts = items.filter((i) => i.status !== "published");
  const published = items.filter((i) => i.status === "published");

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.accent.purple} />
        <Text style={styles.loadingText}>Loading studio...</Text>
      </View>
    );
  }

  const renderItem = (item: StudioItemList) => {
    const sc = statusColors[item.status] ?? statusColors.draft;
    const typeColor =
      contentTypeColors[item.contentType as ContentType] ?? colors.text.muted;

    return (
      <TouchableOpacity
        key={item.id}
        style={styles.card}
        onPress={() => router.push(`/studio/${item.slug}`)}
        activeOpacity={0.7}
      >
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle} numberOfLines={2}>
            {item.title}
          </Text>
          <View style={[styles.statusBadge, { backgroundColor: sc.bg }]}>
            <Text style={[styles.statusText, { color: sc.text }]}>
              {item.status}
            </Text>
          </View>
        </View>

        <View style={styles.cardMeta}>
          <View style={[styles.typeBadge, { backgroundColor: `${typeColor}20` }]}>
            <Text style={[styles.typeText, { color: typeColor }]}>
              {item.contentType}
            </Text>
          </View>
          <Text style={styles.dateText}>{formatDate(item.updatedAt)}</Text>
        </View>

        {(item.platformsReady > 0 || item.platformsPublished > 0) && (
          <View style={styles.platformCounts}>
            {item.platformsReady > 0 && (
              <Text style={styles.platformCountText}>
                {item.platformsReady} ready
              </Text>
            )}
            {item.platformsPublished > 0 && (
              <Text style={styles.platformPublishedText}>
                {item.platformsPublished} published
              </Text>
            )}
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.accent.purple}
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.heading}>Content Studio</Text>
          <TouchableOpacity
            style={styles.newButton}
            onPress={() => setModalVisible(true)}
            activeOpacity={0.8}
          >
            <Plus size={18} color={colors.text.primary} />
            <Text style={styles.newButtonText}>New Post</Text>
          </TouchableOpacity>
        </View>

        {items.length === 0 ? (
          <View style={styles.emptyContainer}>
            <PenLine size={48} color={colors.text.dimmed} />
            <Text style={styles.emptyTitle}>No content yet</Text>
            <Text style={styles.emptySubtitle}>
              Create your first post to get started.
            </Text>
          </View>
        ) : (
          <>
            {/* Drafts */}
            {drafts.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>
                  Drafts ({drafts.length})
                </Text>
                {drafts.map(renderItem)}
              </View>
            )}

            {/* Published */}
            {published.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>
                  Published ({published.length})
                </Text>
                {published.map(renderItem)}
              </View>
            )}
          </>
        )}
      </ScrollView>

      {/* New Post Modal */}
      <Modal
        visible={modalVisible}
        animationType="slide"
        transparent
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { paddingBottom: Math.max(insets.bottom, 16) + 24 }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>New Post</Text>
              <TouchableOpacity
                onPress={() => setModalVisible(false)}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <X size={24} color={colors.text.muted} />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Title</Text>
            <TextInput
              style={styles.textInput}
              value={newTitle}
              onChangeText={setNewTitle}
              placeholder="Enter a title..."
              placeholderTextColor={colors.text.muted}
              autoFocus
            />

            <Text style={styles.inputLabel}>Content Type</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.pillRow}
            >
              {CONTENT_TYPES.map((ct) => {
                const isActive = newContentType === ct;
                const pillColor = contentTypeColors[ct];
                return (
                  <TouchableOpacity
                    key={ct}
                    style={[
                      styles.pill,
                      isActive && { backgroundColor: pillColor },
                      !isActive && {
                        backgroundColor: `${pillColor}20`,
                        borderWidth: 1,
                        borderColor: `${pillColor}40`,
                      },
                    ]}
                    onPress={() => setNewContentType(ct)}
                    activeOpacity={0.7}
                  >
                    <Text
                      style={[
                        styles.pillText,
                        isActive && { color: colors.text.primary },
                        !isActive && { color: pillColor },
                      ]}
                    >
                      {ct}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            <TouchableOpacity
              style={[
                styles.createButton,
                (!newTitle.trim() || creating) && styles.createButtonDisabled,
              ]}
              onPress={handleCreate}
              disabled={!newTitle.trim() || creating}
              activeOpacity={0.8}
            >
              {creating ? (
                <ActivityIndicator size="small" color={colors.text.primary} />
              ) : (
                <Text style={styles.createButtonText}>Create</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  heading: {
    fontSize: 24,
    fontWeight: "700",
    color: colors.text.primary,
  },
  newButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 10,
    backgroundColor: colors.accent.purple,
  },
  newButtonText: {
    color: colors.text.primary,
    fontSize: 14,
    fontWeight: "600",
  },
  emptyContainer: {
    alignItems: "center",
    paddingTop: 60,
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
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text.secondary,
    marginBottom: 12,
  },
  card: {
    padding: 16,
    borderRadius: 16,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    marginBottom: 12,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 10,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text.primary,
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    flexShrink: 0,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "500",
    textTransform: "capitalize",
  },
  cardMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 10,
  },
  typeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  typeText: {
    fontSize: 12,
    fontWeight: "500",
    textTransform: "capitalize",
  },
  dateText: {
    fontSize: 12,
    color: colors.text.muted,
  },
  platformCounts: {
    flexDirection: "row",
    gap: 12,
    marginTop: 10,
  },
  platformCountText: {
    fontSize: 12,
    color: colors.accent.blue,
  },
  platformPublishedText: {
    fontSize: 12,
    color: colors.accent.green,
  },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: colors.bg.secondary,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: colors.text.primary,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text.secondary,
    marginBottom: 8,
  },
  textInput: {
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.bg.tertiary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
    color: colors.text.primary,
    fontSize: 16,
    marginBottom: 20,
  },
  pillRow: {
    marginBottom: 24,
    flexGrow: 0,
  },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 8,
  },
  pillText: {
    fontSize: 14,
    fontWeight: "500",
    textTransform: "capitalize",
  },
  createButton: {
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: colors.accent.purple,
    alignItems: "center",
  },
  createButtonDisabled: {
    opacity: 0.5,
  },
  createButtonText: {
    color: colors.text.primary,
    fontSize: 16,
    fontWeight: "600",
  },
});
