"use client";

import { useGameStore } from "@/store/useGameStore";
import { AudioButton } from "./AudioButton";
import type { GameTurnCharacter, WinCondition } from "@/lib/types";

// Short stat name used in win_conditions -> the canonical key in character.stats
const STAT_KEY: Record<string, string> = {
  trust: "trust_towards_player",
  familiarity: "familiarity_towards_player",
  respect: "respect_towards_player",
  suspicion: "suspicion_towards_player",
  rapport: "rapport_towards_player",
  disclosure_level: "disclosure_level",
  stress: "stress",
};

const STAT_LABEL: Record<string, string> = {
  trust: "Trust",
  familiarity: "Familiarity",
  respect: "Respect",
  suspicion: "Suspicion",
  rapport: "Rapport",
  disclosure_level: "Disclosure",
  stress: "Stress",
};

function winProgress(
  chars: GameTurnCharacter[],
  conds: WinCondition[],
): { current: number; target: number; label: string }[] {
  return conds
    .map((c) => {
      const key = STAT_KEY[c.stat] ?? c.stat;
      const value = chars.find((ch) => ch.id === c.character)?.stats?.[key];
      if (value == null) return null;
      const target = c.min ?? c.max ?? 0;
      const label = `${STAT_LABEL[c.stat] ?? c.stat} ${value}/${target}`;
      // For a "max" goal (e.g. drop suspicion to 3) progress counts the drop.
      const current = c.min != null ? value : 10 - value;
      const goal = c.min != null ? target : 10 - target;
      return { current, target: goal, label };
    })
    .filter((x): x is { current: number; target: number; label: string } => x !== null);
}

export function TopBar() {
  const mission = useGameStore((s) => s.mission);
  const player = useGameStore((s) => s.player);
  const characters = useGameStore((s) => s.characters);
  const gameState = useGameStore((s) => s.gameState);

  const progress =
    mission?.win_conditions?.length && gameState === "live_mission"
      ? winProgress(characters, mission.win_conditions)
      : [];

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-edge bg-surface px-4">
      <div className="flex min-w-0 items-center gap-3">
        <span className="text-sm font-bold tracking-tight text-ink">KRYPTON</span>
        {player && (
          <span className="hidden text-xs text-muted md:inline">
            {player.character_name} · {player.world_choice}
          </span>
        )}
        {mission && (
          <div className="hidden min-w-0 items-center gap-2 rounded-full border border-edge bg-surface-2 px-3 py-1 text-xs text-muted lg:flex">
            <span className="shrink-0 text-accent">M{mission.id}</span>
            <span className="max-w-[180px] truncate">{mission.title}</span>
            {mission.location && (
              <>
                <span className="text-edge">|</span>
                <span className="max-w-[140px] truncate">📍 {mission.location}</span>
              </>
            )}
            {mission.objective && (
              <>
                <span className="text-edge">|</span>
                <span className="max-w-[240px] truncate text-ink/80">
                  🎯 {mission.objective}
                </span>
              </>
            )}
            <span className="text-muted/60">{mission.chain_progress}</span>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {progress.length > 0 && (
          <div className="hidden items-center gap-1.5 sm:flex">
            {progress.map((p) => (
              <span
                key={p.label}
                className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                  p.current >= p.target
                    ? "border-trust/40 bg-trust/10 text-trust"
                    : "border-edge bg-surface-2 text-muted"
                }`}
              >
                {p.label}
              </span>
            ))}
          </div>
        )}
        <AudioButton />
      </div>
    </header>
  );
}
