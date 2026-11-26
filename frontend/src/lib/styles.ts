// Shared style tokens used by several components.

// Okabe-Ito hues (colour-blind safe), softened for chips; always rendered with a text label.
export const SOFT = {
  critical: { bg: "#fdeee6", fg: "#a34000", dot: "#D55E00" },
  high: { bg: "#fdf4e3", fg: "#8a5800", dot: "#E69F00" },
  medium: { bg: "#e9f4fb", fg: "#1d6a96", dot: "#56B4E9" },
  low: { bg: "#e5f5ee", fg: "#0b6b49", dot: "#009E73" },
  warning: { bg: "#fbf8dc", fg: "#6f6400", dot: "#C9B800" },
  info: { bg: "#f1f1f3", fg: "#52525b", dot: "#a1a1aa" },
} as const;

export const inputCls = "h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink placeholder:text-faint focus:border-accent focus:outline-none";
