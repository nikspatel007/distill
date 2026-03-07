import { useEffect, useState, useCallback, useRef } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Image,
} from "react-native";
import {
  ArrowLeft,
  Trash2,
  ChevronDown,
  ChevronUp,
  Send,
  ImagePlus,
} from "lucide-react-native";
import { useRouter, useLocalSearchParams } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { apiFetch } from "../../lib/api";
import { colors } from "../../lib/colors";
import type { StudioItem, StudioImage } from "@distill/shared";

// --- Types ---

interface PlatformInfo {
  id: string;
  name: string;
}

interface GhostTarget {
  id: string;
  name: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

// --- Constants ---

const PLATFORM_TABS = ["source", "linkedin", "x", "ghost", "reddit"] as const;
type PlatformTab = (typeof PLATFORM_TABS)[number];

const CHAR_LIMITS: Partial<Record<PlatformTab, number>> = {
  x: 280,
  linkedin: 3000,
};

const SUGGESTION_CHIPS = [
  "Adapt for LinkedIn",
  "Shorten for X",
  "Add a hook",
];

const MOODS = [
  "reflective",
  "energetic",
  "cautionary",
  "triumphant",
  "intimate",
  "technical",
  "playful",
  "somber",
] as const;

const statusColors: Record<string, { bg: string; text: string }> = {
  draft: { bg: "rgba(107, 114, 128, 0.15)", text: colors.text.muted },
  ready: { bg: "rgba(96, 165, 250, 0.15)", text: colors.accent.blue },
  published: { bg: "rgba(74, 222, 128, 0.15)", text: colors.accent.green },
};

// --- Component ---

export default function StudioDetailScreen() {
  const router = useRouter();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const insets = useSafeAreaInsets();

  // Core state
  const [item, setItem] = useState<StudioItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Platform tabs
  const [activePlatform, setActivePlatform] = useState<PlatformTab>("source");

  // Publish section
  const [publishExpanded, setPublishExpanded] = useState(false);
  const [postizPlatforms, setPostizPlatforms] = useState<PlatformInfo[]>([]);
  const [ghostTargets, setGhostTargets] = useState<GhostTarget[]>([]);
  const [publishing, setPublishing] = useState<string | null>(null);

  // Chat section
  const [chatExpanded, setChatExpanded] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const chatScrollRef = useRef<ScrollView>(null);

  // Images section
  const [imagesExpanded, setImagesExpanded] = useState(false);
  const [images, setImages] = useState<StudioImage[]>([]);
  const [generatingImages, setGeneratingImages] = useState(false);
  const [selectedMood, setSelectedMood] = useState<string>("reflective");

  // --- Data loading ---

  const loadItem = useCallback(async () => {
    if (!slug) return;
    try {
      const data = await apiFetch<StudioItem & { images: StudioImage[] }>(`/studio/items/${slug}`);
      setItem(data);
      setImages(data.images ?? []);
      if (data.chatHistory) {
        setChatMessages(data.chatHistory);
      }
    } catch (err) {
      console.error("Failed to load studio item:", err);
    }
  }, [slug]);

  const loadPlatforms = useCallback(async () => {
    try {
      const data = await apiFetch<{ integrations: PlatformInfo[]; configured: boolean }>("/studio/platforms");
      setPostizPlatforms(data.integrations);
    } catch (_err) {
      // Platforms may not be configured
    }
  }, []);

  const loadGhostTargets = useCallback(async () => {
    try {
      const data = await apiFetch<{ targets: GhostTarget[] }>("/studio/ghost/targets");
      setGhostTargets(data.targets);
    } catch (_err) {
      // Ghost may not be configured
    }
  }, []);

  useEffect(() => {
    Promise.all([loadItem(), loadPlatforms(), loadGhostTargets()])
      .finally(() => setLoading(false));
  }, [loadItem, loadPlatforms, loadGhostTargets]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([loadItem(), loadImages()]);
    setRefreshing(false);
  }, [loadItem, loadImages]);

  // --- Actions ---

  const handleDelete = () => {
    Alert.alert("Delete Post", "Are you sure you want to delete this post?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await apiFetch(`/studio/items/${slug}`, { method: "DELETE" });
            router.back();
          } catch (err) {
            Alert.alert("Error", "Failed to delete item.");
            console.error("Failed to delete:", err);
          }
        },
      },
    ]);
  };

  const handlePublishPostiz = async (platformId: string) => {
    if (!slug) return;
    setPublishing(platformId);
    try {
      await apiFetch(`/studio/publish/${slug}`, {
        method: "POST",
        body: JSON.stringify({
          platforms: [platformId],
          mode: "draft",
        }),
      });
      Alert.alert("Success", "Draft pushed to Postiz.");
      await loadItem();
    } catch (err) {
      Alert.alert("Error", "Failed to publish.");
      console.error("Publish error:", err);
    } finally {
      setPublishing(null);
    }
  };

  const handlePublishGhost = async (
    targetId: string,
    status: "draft" | "published"
  ) => {
    if (!slug) return;
    setPublishing(targetId);
    try {
      await apiFetch(`/studio/ghost/publish/${slug}`, {
        method: "POST",
        body: JSON.stringify({
          target: targetId,
          status,
          tags: item?.tags ?? [],
        }),
      });
      Alert.alert(
        "Success",
        status === "draft" ? "Ghost draft created." : "Published to Ghost."
      );
      await loadItem();
    } catch (err) {
      Alert.alert("Error", "Failed to publish to Ghost.");
      console.error("Ghost publish error:", err);
    } finally {
      setPublishing(null);
    }
  };

  const handleSendChat = async (message?: string) => {
    const text = message ?? chatInput.trim();
    if (!text || !slug) return;

    const userMessage: ChatMessage = {
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");
    setChatSending(true);

    try {
      const platformContent = getPlatformContent();
      const headers = {
        "Content-Type": "application/json",
      } as Record<string, string>;
      const { data: session } = await (await import("../../lib/supabase")).supabase.auth.getSession();
      if (session.session?.access_token) {
        headers["Authorization"] = `Bearer ${session.session.access_token}`;
      }
      const apiUrl = process.env.EXPO_PUBLIC_API_URL ?? "";
      const res = await fetch(`${apiUrl}/api/studio/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          messages: [...chatMessages, userMessage],
          content: platformContent,
          platform: activePlatform === "source" ? "source" : activePlatform,
          slug,
        }),
      });

      if (!res.ok) throw new Error(`Chat API error: ${res.status}`);

      // Consume SSE stream and collect text deltas
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let assistantText = "";

      if (reader) {
        let done = false;
        while (!done) {
          const { value, done: streamDone } = await reader.read();
          done = streamDone;
          if (value) {
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split("\n");
            for (const line of lines) {
              if (!line.startsWith("data: ")) continue;
              const jsonStr = line.slice(6);
              if (jsonStr === "[DONE]") continue;
              try {
                const parsed = JSON.parse(jsonStr);
                if (parsed.type === "text-delta" && parsed.delta) {
                  assistantText += parsed.delta;
                }
              } catch {
                // skip unparseable lines
              }
            }
          }
        }
      }

      if (assistantText) {
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: assistantText,
          timestamp: new Date().toISOString(),
        };
        setChatMessages((prev) => [...prev, assistantMessage]);
      }

      // Refetch item to pick up any platform content updates from tool calls
      await loadItem();
    } catch (err) {
      Alert.alert("Error", "Failed to send message.");
      console.error("Chat error:", err);
    } finally {
      setChatSending(false);
    }
  };

  const handleGenerateImages = async () => {
    if (!slug) return;
    setGeneratingImages(true);
    try {
      await apiFetch(`/studio/items/${slug}/images/batch`, {
        method: "POST",
        body: JSON.stringify({
          prompt: item?.title ?? "Generate images",
          mood: selectedMood,
        }),
      });
      await loadItem();
    } catch (err) {
      Alert.alert("Error", "Failed to generate images.");
      console.error("Image generation error:", err);
    } finally {
      setGeneratingImages(false);
    }
  };

  // --- Helpers ---

  const getPlatformContent = (): string => {
    if (!item) return "";
    if (activePlatform === "source") return item.content ?? "";
    const entry = item.platformContents?.[activePlatform];
    return entry?.content ?? "";
  };

  const getCharLimit = (): number | null => {
    return CHAR_LIMITS[activePlatform] ?? null;
  };

  // --- Render ---

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.accent.purple} />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!item) {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>Item not found</Text>
        <TouchableOpacity
          style={styles.backButtonEmpty}
          onPress={() => router.back()}
        >
          <Text style={styles.backButtonEmptyText}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const sc = statusColors[item.status] ?? statusColors.draft;
  const currentContent = getPlatformContent();
  const charLimit = getCharLimit();
  const charRatio = charLimit ? currentContent.length / charLimit : 0;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={insets.top}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.accent.purple}
          />
        }
      >
        {/* Header */}
        <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
          <TouchableOpacity
            onPress={() => router.back()}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            style={styles.headerBackButton}
          >
            <ArrowLeft size={24} color={colors.text.primary} />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle} numberOfLines={1}>
              {item.title}
            </Text>
            <View style={[styles.headerStatusBadge, { backgroundColor: sc.bg }]}>
              <Text style={[styles.headerStatusText, { color: sc.text }]}>
                {item.status}
              </Text>
            </View>
          </View>
          <TouchableOpacity
            onPress={handleDelete}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Trash2 size={20} color={colors.accent.red} />
          </TouchableOpacity>
        </View>

        {/* Platform Tabs */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.platformTabsContainer}
          contentContainerStyle={styles.platformTabs}
        >
          {PLATFORM_TABS.map((tab) => {
            const isActive = activePlatform === tab;
            const label = tab === "source" ? "Source" : tab.charAt(0).toUpperCase() + tab.slice(1);
            const entry = tab !== "source" ? item.platformContents?.[tab] : null;
            const isPublished = entry?.published ?? false;

            return (
              <TouchableOpacity
                key={tab}
                style={[
                  styles.platformTab,
                  isActive && styles.platformTabActive,
                ]}
                onPress={() => setActivePlatform(tab)}
                activeOpacity={0.7}
              >
                <Text
                  style={[
                    styles.platformTabText,
                    isActive && styles.platformTabTextActive,
                  ]}
                >
                  {label}
                </Text>
                {isPublished && <View style={styles.publishedDot} />}
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Content */}
        <View style={styles.contentSection}>
          {currentContent ? (
            <>
              <Text style={styles.contentText}>{currentContent}</Text>
              {charLimit && (
                <View style={styles.charLimitContainer}>
                  <View style={styles.charLimitBar}>
                    <View
                      style={[
                        styles.charLimitFill,
                        {
                          width: `${Math.min(charRatio * 100, 100)}%`,
                          backgroundColor:
                            charRatio > 1
                              ? colors.accent.red
                              : charRatio > 0.9
                                ? colors.accent.amber
                                : colors.accent.green,
                        },
                      ]}
                    />
                  </View>
                  <Text
                    style={[
                      styles.charLimitText,
                      charRatio > 1 && { color: colors.accent.red },
                    ]}
                  >
                    {currentContent.length}/{charLimit}
                  </Text>
                </View>
              )}
            </>
          ) : (
            <View style={styles.noContentContainer}>
              <Text style={styles.noContentText}>
                {activePlatform === "source"
                  ? "No source content yet. Use the chat to generate content."
                  : `No ${activePlatform} content yet. Use the chat to adapt your content.`}
              </Text>
            </View>
          )}
        </View>

        {/* Publish Section (collapsible) */}
        <TouchableOpacity
          style={styles.collapsibleHeader}
          onPress={() => setPublishExpanded(!publishExpanded)}
          activeOpacity={0.7}
        >
          <Text style={styles.collapsibleTitle}>Publish</Text>
          {publishExpanded ? (
            <ChevronUp size={20} color={colors.text.muted} />
          ) : (
            <ChevronDown size={20} color={colors.text.muted} />
          )}
        </TouchableOpacity>

        {publishExpanded && (
          <View style={styles.collapsibleContent}>
            {/* Postiz platforms */}
            {postizPlatforms.length > 0 && (
              <View style={styles.publishGroup}>
                <Text style={styles.publishGroupTitle}>Postiz</Text>
                {postizPlatforms.map((p) => (
                  <View key={p.id} style={styles.publishRow}>
                    <Text style={styles.publishPlatformName}>{p.name}</Text>
                    <TouchableOpacity
                      style={styles.publishButton}
                      onPress={() => handlePublishPostiz(p.id)}
                      disabled={publishing === p.id}
                      activeOpacity={0.7}
                    >
                      {publishing === p.id ? (
                        <ActivityIndicator
                          size="small"
                          color={colors.text.primary}
                        />
                      ) : (
                        <Text style={styles.publishButtonText}>Publish</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            )}

            {/* Ghost targets */}
            {ghostTargets.length > 0 && (
              <View style={styles.publishGroup}>
                <Text style={styles.publishGroupTitle}>Ghost</Text>
                {ghostTargets.map((t) => (
                  <View key={t.id} style={styles.publishRow}>
                    <Text style={styles.publishPlatformName}>{t.name}</Text>
                    <View style={styles.ghostButtons}>
                      <TouchableOpacity
                        style={[styles.publishButton, styles.publishButtonSmall]}
                        onPress={() => handlePublishGhost(t.id, "draft")}
                        disabled={publishing === t.id}
                        activeOpacity={0.7}
                      >
                        <Text style={styles.publishButtonText}>Draft</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[
                          styles.publishButton,
                          styles.publishButtonSmall,
                          styles.publishButtonGreen,
                        ]}
                        onPress={() => handlePublishGhost(t.id, "published")}
                        disabled={publishing === t.id}
                        activeOpacity={0.7}
                      >
                        <Text style={styles.publishButtonText}>Publish</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            )}

            {postizPlatforms.length === 0 && ghostTargets.length === 0 && (
              <Text style={styles.noPublishText}>
                No publishing platforms configured.
              </Text>
            )}
          </View>
        )}

        {/* Images Section (collapsible) */}
        <TouchableOpacity
          style={styles.collapsibleHeader}
          onPress={() => setImagesExpanded(!imagesExpanded)}
          activeOpacity={0.7}
        >
          <Text style={styles.collapsibleTitle}>Images</Text>
          {imagesExpanded ? (
            <ChevronUp size={20} color={colors.text.muted} />
          ) : (
            <ChevronDown size={20} color={colors.text.muted} />
          )}
        </TouchableOpacity>

        {imagesExpanded && (
          <View style={styles.collapsibleContent}>
            {images.length > 0 && (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                style={styles.imagesRow}
              >
                {images.map((img) => (
                  <View key={img.id} style={styles.imageThumb}>
                    <Image
                      source={{ uri: img.url }}
                      style={styles.imageThumbImg}
                      resizeMode="cover"
                    />
                    <Text style={styles.imageRole}>{img.role}</Text>
                  </View>
                ))}
              </ScrollView>
            )}

            <Text style={styles.inputLabel}>Mood</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.moodRow}
            >
              {MOODS.map((mood) => {
                const isActive = selectedMood === mood;
                return (
                  <TouchableOpacity
                    key={mood}
                    style={[
                      styles.moodPill,
                      isActive && styles.moodPillActive,
                    ]}
                    onPress={() => setSelectedMood(mood)}
                    activeOpacity={0.7}
                  >
                    <Text
                      style={[
                        styles.moodPillText,
                        isActive && styles.moodPillTextActive,
                      ]}
                    >
                      {mood}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            <TouchableOpacity
              style={[
                styles.generateButton,
                generatingImages && styles.generateButtonDisabled,
              ]}
              onPress={handleGenerateImages}
              disabled={generatingImages}
              activeOpacity={0.8}
            >
              {generatingImages ? (
                <ActivityIndicator size="small" color={colors.text.primary} />
              ) : (
                <>
                  <ImagePlus size={18} color={colors.text.primary} />
                  <Text style={styles.generateButtonText}>Generate</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* AI Chat Section (collapsible) */}
        <TouchableOpacity
          style={styles.collapsibleHeader}
          onPress={() => setChatExpanded(!chatExpanded)}
          activeOpacity={0.7}
        >
          <Text style={styles.collapsibleTitle}>AI Chat</Text>
          {chatExpanded ? (
            <ChevronUp size={20} color={colors.text.muted} />
          ) : (
            <ChevronDown size={20} color={colors.text.muted} />
          )}
        </TouchableOpacity>

        {chatExpanded && (
          <View style={styles.collapsibleContent}>
            {/* Suggestion chips */}
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.chipsRow}
            >
              {SUGGESTION_CHIPS.map((chip) => (
                <TouchableOpacity
                  key={chip}
                  style={styles.chip}
                  onPress={() => handleSendChat(chip)}
                  disabled={chatSending}
                  activeOpacity={0.7}
                >
                  <Text style={styles.chipText}>{chip}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Message list */}
            {chatMessages.length > 0 && (
              <ScrollView
                ref={chatScrollRef}
                style={styles.chatMessages}
                nestedScrollEnabled
                onContentSizeChange={() =>
                  chatScrollRef.current?.scrollToEnd({ animated: true })
                }
              >
                {chatMessages.map((msg, i) => (
                  <View
                    key={i}
                    style={[
                      styles.chatBubble,
                      msg.role === "user"
                        ? styles.chatBubbleUser
                        : styles.chatBubbleAssistant,
                    ]}
                  >
                    <Text
                      style={[
                        styles.chatBubbleText,
                        msg.role === "user"
                          ? styles.chatBubbleTextUser
                          : styles.chatBubbleTextAssistant,
                      ]}
                    >
                      {msg.content}
                    </Text>
                  </View>
                ))}
                {chatSending && (
                  <View style={[styles.chatBubble, styles.chatBubbleAssistant]}>
                    <ActivityIndicator
                      size="small"
                      color={colors.accent.purple}
                    />
                  </View>
                )}
              </ScrollView>
            )}

            {/* Chat input */}
            <View style={styles.chatInputRow}>
              <TextInput
                style={styles.chatInput}
                value={chatInput}
                onChangeText={setChatInput}
                placeholder="Ask AI to help with your content..."
                placeholderTextColor={colors.text.muted}
                multiline
                maxLength={2000}
              />
              <TouchableOpacity
                style={[
                  styles.chatSendButton,
                  (!chatInput.trim() || chatSending) &&
                    styles.chatSendButtonDisabled,
                ]}
                onPress={() => handleSendChat()}
                disabled={!chatInput.trim() || chatSending}
                activeOpacity={0.7}
              >
                <Send size={18} color={colors.text.primary} />
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Bottom spacing */}
        <View style={styles.bottomSpacer} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg.primary,
  },
  scrollContent: {
    paddingBottom: 40,
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
    marginBottom: 16,
  },
  backButtonEmpty: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 10,
    backgroundColor: colors.bg.tertiary,
  },
  backButtonEmptyText: {
    color: colors.text.primary,
    fontSize: 14,
    fontWeight: "500",
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingTop: 0, // overridden by dynamic insets.top + 8
    paddingBottom: 16,
    backgroundColor: colors.bg.primary,
  },
  headerBackButton: {
    flexShrink: 0,
  },
  headerCenter: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text.primary,
    flexShrink: 1,
  },
  headerStatusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    flexShrink: 0,
  },
  headerStatusText: {
    fontSize: 11,
    fontWeight: "500",
    textTransform: "capitalize",
  },

  // Platform Tabs
  platformTabsContainer: {
    flexGrow: 0,
    marginBottom: 4,
  },
  platformTabs: {
    paddingHorizontal: 16,
    gap: 8,
    flexDirection: "row",
  },
  platformTab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.bg.tertiary,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  platformTabActive: {
    backgroundColor: colors.accent.purple,
  },
  platformTabText: {
    fontSize: 14,
    fontWeight: "500",
    color: colors.text.muted,
  },
  platformTabTextActive: {
    color: colors.text.primary,
  },
  publishedDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.accent.green,
  },

  // Content
  contentSection: {
    padding: 16,
  },
  contentText: {
    fontSize: 15,
    color: colors.text.secondary,
    lineHeight: 22,
  },
  charLimitContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginTop: 12,
  },
  charLimitBar: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.bg.tertiary,
    overflow: "hidden",
  },
  charLimitFill: {
    height: "100%",
    borderRadius: 2,
  },
  charLimitText: {
    fontSize: 12,
    color: colors.text.muted,
    flexShrink: 0,
  },
  noContentContainer: {
    paddingVertical: 32,
    alignItems: "center",
  },
  noContentText: {
    fontSize: 14,
    color: colors.text.muted,
    textAlign: "center",
  },

  // Collapsible sections
  collapsibleHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: colors.border.primary,
  },
  collapsibleTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text.primary,
  },
  collapsibleContent: {
    paddingHorizontal: 16,
    paddingBottom: 16,
  },

  // Publish
  publishGroup: {
    marginBottom: 16,
  },
  publishGroupTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text.tertiary,
    marginBottom: 8,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  publishRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    marginBottom: 8,
  },
  publishPlatformName: {
    fontSize: 14,
    color: colors.text.primary,
    fontWeight: "500",
  },
  publishButton: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: colors.accent.purple,
  },
  publishButtonSmall: {
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  publishButtonGreen: {
    backgroundColor: colors.accent.green,
  },
  publishButtonText: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.text.primary,
  },
  ghostButtons: {
    flexDirection: "row",
    gap: 8,
  },
  noPublishText: {
    fontSize: 14,
    color: colors.text.muted,
    textAlign: "center",
    paddingVertical: 12,
  },

  // Images
  imagesRow: {
    marginBottom: 16,
    flexGrow: 0,
  },
  imageThumb: {
    width: 120,
    height: 120,
    borderRadius: 12,
    marginRight: 10,
    overflow: "hidden",
    backgroundColor: colors.bg.tertiary,
  },
  imageThumbImg: {
    width: "100%",
    height: "100%",
  },
  imageRole: {
    position: "absolute",
    bottom: 4,
    left: 4,
    fontSize: 10,
    fontWeight: "600",
    color: colors.text.primary,
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    textTransform: "capitalize",
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text.secondary,
    marginBottom: 8,
  },
  moodRow: {
    marginBottom: 16,
    flexGrow: 0,
  },
  moodPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.bg.tertiary,
    marginRight: 8,
    borderWidth: 1,
    borderColor: colors.border.secondary,
  },
  moodPillActive: {
    backgroundColor: colors.accent.purple,
    borderColor: colors.accent.purple,
  },
  moodPillText: {
    fontSize: 13,
    color: colors.text.muted,
    textTransform: "capitalize",
  },
  moodPillTextActive: {
    color: colors.text.primary,
  },
  generateButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: colors.accent.purple,
  },
  generateButtonDisabled: {
    opacity: 0.5,
  },
  generateButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text.primary,
  },

  // Chat
  chipsRow: {
    marginBottom: 12,
    flexGrow: 0,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.bg.tertiary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
    marginRight: 8,
  },
  chipText: {
    fontSize: 13,
    color: colors.accent.purpleLight,
  },
  chatMessages: {
    maxHeight: 300,
    marginBottom: 12,
  },
  chatBubble: {
    padding: 12,
    borderRadius: 14,
    marginBottom: 8,
    maxWidth: "85%",
  },
  chatBubbleUser: {
    backgroundColor: colors.accent.purple,
    alignSelf: "flex-end",
    borderBottomRightRadius: 4,
  },
  chatBubbleAssistant: {
    backgroundColor: colors.bg.tertiary,
    alignSelf: "flex-start",
    borderBottomLeftRadius: 4,
  },
  chatBubbleText: {
    fontSize: 14,
    lineHeight: 20,
  },
  chatBubbleTextUser: {
    color: colors.text.primary,
  },
  chatBubbleTextAssistant: {
    color: colors.text.secondary,
  },
  chatInputRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-end",
  },
  chatInput: {
    flex: 1,
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.bg.tertiary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
    color: colors.text.primary,
    fontSize: 14,
    maxHeight: 100,
  },
  chatSendButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: colors.accent.purple,
    justifyContent: "center",
    alignItems: "center",
  },
  chatSendButtonDisabled: {
    opacity: 0.4,
  },

  bottomSpacer: {
    height: 20,
  },
});
