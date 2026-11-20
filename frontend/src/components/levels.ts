/** Level metadata: colour + shape + word (doc 15 §2.3, doc 11 §4). */
export type Level = "NORMAL" | "ELEVATED" | "HIGH" | "CRITICAL";

export const LEVELS: Record<Level, { label: string; shape: string; colour: string }> = {
  NORMAL: { label: "Normal", shape: "●", colour: "var(--lvl-normal)" },
  ELEVATED: { label: "Elevated", shape: "▲", colour: "var(--lvl-elevated)" },
  HIGH: { label: "High", shape: "◆", colour: "var(--lvl-high)" },
  CRITICAL: { label: "Critical", shape: "■", colour: "var(--lvl-critical)" },
};
