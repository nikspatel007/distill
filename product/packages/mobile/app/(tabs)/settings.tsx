import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from "react-native";
import { LogOut, User, Mail } from "lucide-react-native";
import { useAuth } from "../../lib/auth";
import { colors } from "../../lib/colors";

export default function SettingsScreen() {
  const { user, signOut } = useAuth();

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      {/* Profile card */}
      <View style={styles.profileCard}>
        <View style={styles.avatarLarge}>
          <User size={32} color={colors.text.secondary} />
        </View>
        <View style={styles.profileInfo}>
          <Text style={styles.profileName}>
            {user?.user_metadata?.["full_name"] ??
              user?.user_metadata?.["name"] ??
              "User"}
          </Text>
          {user?.email && (
            <View style={styles.emailRow}>
              <Mail size={14} color={colors.text.muted} />
              <Text style={styles.profileEmail}>{user.email}</Text>
            </View>
          )}
        </View>
      </View>

      {/* Account section */}
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>Account</Text>

        <TouchableOpacity
          style={styles.menuItem}
          onPress={signOut}
          activeOpacity={0.7}
        >
          <LogOut size={20} color={colors.accent.red} />
          <Text style={styles.menuItemTextDanger}>Sign Out</Text>
        </TouchableOpacity>
      </View>

      {/* App info */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>Distill v1.0.0</Text>
        <Text style={styles.footerText}>Personal Intelligence Platform</Text>
      </View>
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
  profileCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    padding: 20,
    borderRadius: 16,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
    marginBottom: 24,
  },
  avatarLarge: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.bg.tertiary,
    justifyContent: "center",
    alignItems: "center",
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text.primary,
    marginBottom: 4,
  },
  emailRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  profileEmail: {
    fontSize: 14,
    color: colors.text.muted,
  },
  section: {
    marginBottom: 24,
  },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    color: colors.text.muted,
    marginBottom: 8,
  },
  menuItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.bg.card,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  menuItemTextDanger: {
    fontSize: 16,
    fontWeight: "500",
    color: colors.accent.red,
  },
  footer: {
    alignItems: "center",
    marginTop: 40,
    gap: 4,
  },
  footerText: {
    fontSize: 13,
    color: colors.text.dimmed,
  },
});
