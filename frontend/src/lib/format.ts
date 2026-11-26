// Colour-blind-safe severity palette (Okabe-Ito). Severity is never shown by colour alone:
// every badge also carries a text label and an icon shape.
export const SEV = {
  critical: { color: "#D55E00", bg: "bg-[#D55E00]", text: "text-white", ring: "ring-[#D55E00]", shape: "▲" },
  high: { color: "#E69F00", bg: "bg-[#E69F00]", text: "text-black", ring: "ring-[#E69F00]", shape: "◆" },
  medium: { color: "#56B4E9", bg: "bg-[#56B4E9]", text: "text-black", ring: "ring-[#56B4E9]", shape: "●" },
  low: { color: "#009E73", bg: "bg-[#009E73]", text: "text-white", ring: "ring-[#009E73]", shape: "■" },
  warning: { color: "#F0E442", bg: "bg-[#F0E442]", text: "text-black", ring: "ring-[#F0E442]", shape: "!" },
  info: { color: "#999999", bg: "bg-gray-400", text: "text-white", ring: "ring-gray-400", shape: "i" },
} as const;
export type Sev = keyof typeof SEV;

export const pct = (p: number | null | undefined) => (p == null ? "-" : `${Math.round(p * 100)}%`);
export const hrs = (h: number | null | undefined) => {
  if (h == null) return "> 7 days";
  if (h < 1) return "< 1 h";
  if (h < 48) return `${Math.round(h)} h`;
  return `${(h / 24).toFixed(1)} days`;
};
// All timestamps are UTC in the DB and displayed in Asia/Kolkata.
export const ist = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }) : "-";
export const GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"] as const;
export const COMPONENTS = ["RBC", "PLT", "FFP", "CRYO"] as const;
export const COMP_LABEL: Record<string, string> = { RBC: "Red cells", PLT: "Platelets", FFP: "Plasma", CRYO: "Cryo" };
