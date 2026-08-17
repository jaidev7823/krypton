"use client";

import { useGameStore } from "@/store/useGameStore";
import { AudioButton } from "./AudioButton";

export function TopBar() {
  const player = useGameStore((s) => s.player);
  const strategicPlan = useGameStore((s) => s.strategicPlan);
  const mission = useGameStore((s) => s.mission);
  const gameState = useGameStore((s) => s.gameState);
  const toggleCoach = useGameStore((s) => s.toggleCoach);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-edge bg-surface px-4">
      <div className="flex min-w-0 items-center gap-3">
        <span className="text-sm font-bold tracking-tight text-ink">KRYPTON</span>
        {player && (
          <span className="hidden text-xs text-muted md:inline">
            {player.character_name} · {player.world_choice}
          </span>
        )}
        {gameState === "live_scene" && mission && (
          <div className="hidden min-w-0 items-center gap-2 rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs lg:flex">
            <span className="font-semibold text-accent">{mission.title}</span>
            <span className="max-w-[250px] truncate text-muted">{mission.objective}</span>
          </div>
        )}
        {strategicPlan && (
          <div className="hidden min-w-0 items-center gap-2 rounded-full border border-edge bg-surface-2 px-3 py-1 text-xs text-muted lg:flex">
            <span className="max-w-[300px] truncate">{strategicPlan}</span>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={toggleCoach}
          className="rounded-lg border border-edge bg-surface-2 px-3 py-1.5 text-xs font-semibold text-muted transition hover:border-accent/50 hover:text-ink"
          title="Ask the Coach"
        >
          Coach
        </button>
        <AudioButton />
      </div>
    </header>
  );
}
