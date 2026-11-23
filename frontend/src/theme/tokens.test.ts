// Contrast of the level colours (doc 15 §2.1, WCAG 1.4.11 non-text contrast >= 3:1).
// The ratios quoted in doc 15 come from this computation on tokens.css.
import { describe, expect, it } from "vitest";

import css from "./tokens.css?raw";

function relativeLuminance(hex: string): number {
  const channels = [0, 2, 4].map((i) => parseInt(hex.slice(1 + i, 3 + i), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    out[m[1] ?? ""] = (m[2] ?? "").toLowerCase();
  }
  return out;
}

const light = tokens(css.slice(0, css.indexOf("@media")));
const dark = tokens(css.slice(css.indexOf("@media")));
const MARKS = ["lvl-normal", "lvl-elevated", "lvl-high", "lvl-critical", "unknown"];

describe("design tokens", () => {
  it("matches the WCAG reference values", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrast("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
  });

  it.each([
    ["light", light],
    ["dark", dark],
  ])("level and unknown colours reach 3:1 on --bg and --surface (%s)", (_mode, t) => {
    for (const mark of MARKS) {
      for (const surface of ["bg", "surface"]) {
        const ratio = contrast(t[mark] ?? "", t[surface] ?? "");
        expect(ratio, `${mark} on ${surface}`).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it("reproduces the ratios quoted in doc 15", () => {
    const levels = ["lvl-normal", "lvl-elevated", "lvl-high", "lvl-critical"];
    const all = [light, dark].flatMap((t) =>
      levels.flatMap((l) => ["bg", "surface"].map((s) => contrast(t[l] ?? "", t[s] ?? ""))),
    );
    expect(Math.min(...all)).toBeGreaterThanOrEqual(3.4); // lowest: light elevated on --bg
    expect(contrast(light["unknown"] ?? "", light["bg"] ?? "")).toBeCloseTo(3.28, 2);
    expect(contrast("#8a94a6", light["bg"] ?? "")).toBeCloseTo(2.88, 2); // the old --unknown
  });
});
