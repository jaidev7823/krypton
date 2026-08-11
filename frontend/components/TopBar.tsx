"use client";

import { useGameStore } from "@/store/useGameStore";
import { AudioButton } from "./AudioButton";

export function TopBar() {
  const mission = useGameStore((s) => s.mission);
  const player = useGameStore((s) => s.player);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-edge bg-surface px-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold tracking-tight text-ink">KRYPTON</span>
        {player && (
          <span className="hidden text-xs text-muted sm:inline">
            {player.character_name} · {player.world_choice}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {mission && (
          <div className="hidden items-center gap-2 rounded-full border border-edge bg-surface-2 px-3 py-1 text-xs text-muted sm:flex">
            <span className="text-accent">M{mission.id}</span>
            <span className="max-w-[200px] truncate">{mission.title}</span>
            <span className="text-muted/60">{mission.chain_progress}</span>
          </div>
        )}
        <AudioButton />
      </div>
    </header>
  );
}
