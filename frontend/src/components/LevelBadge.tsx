/**
 * The level language (doc 15 §2.3, doc 11 §4): every level is colour + shape + word, so the
 * state never depends on colour alone. Shapes: ● NORMAL, ▲ ELEVATED, ◆ HIGH, ■ CRITICAL.
 */
import { LEVELS, type Level } from "./levels";

export function LevelShape({ level, size = 12 }: { level: Level | null; size?: number }) {
  const meta = level ? LEVELS[level] : null;
  return (
    <span
      aria-hidden="true"
      style={{ color: meta?.colour ?? "var(--unknown)", fontSize: size, lineHeight: 1 }}
    >
      {meta?.shape ?? "○"}
    </span>
  );
}

export function LevelBadge({ level }: { level: Level | null }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-ink">
      <LevelShape level={level} />
      <span>{level ? LEVELS[level].label : "No data"}</span>
    </span>
  );
}
