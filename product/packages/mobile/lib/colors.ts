export const colors = {
  bg: {
    primary: "#030712", // gray-950
    secondary: "#111827", // gray-900
    tertiary: "#1f2937", // gray-800
    card: "#111827",
  },
  text: {
    primary: "#ffffff",
    secondary: "#d1d5db", // gray-300
    tertiary: "#9ca3af", // gray-400
    muted: "#6b7280", // gray-500
    dimmed: "#4b5563", // gray-600
  },
  border: {
    primary: "#1f2937", // gray-800
    secondary: "#374151", // gray-700
  },
  accent: {
    purple: "#a855f7",
    purpleLight: "#c084fc",
    blue: "#60a5fa",
    green: "#4ade80",
    amber: "#fbbf24",
    red: "#f87171",
  },
  status: {
    trending: { bg: "rgba(34, 197, 94, 0.15)", text: "#4ade80" },
    emerging: { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa" },
    cooling: { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24" },
    stable: { bg: "rgba(107, 114, 128, 0.15)", text: "#6b7280" },
  },
  tab: {
    active: "#a855f7",
    inactive: "#6b7280",
  },
} as const;
