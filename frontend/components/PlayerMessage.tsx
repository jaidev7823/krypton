"use client";

import { useGameStore } from "@/store/useGameStore";
import { PFP } from "./PFP";
import type { ChatEntry } from "@/lib/types";

export function PlayerMessage({ entry }: { entry: Extract<ChatEntry, { kind: "message" }> }) {
  const player = useGameStore((s) => s.player);

  return (
    <div className="flex items-start justify-end gap-3">
      <div className="min-w-0 max-w-[85%] text-right">
        <div className="rounded-2xl rounded-tr-sm border border-accent/40 bg-accent/10 px-4 py-3 text-sm leading-relaxed text-ink">
          {entry.text}
        </div>
      </div>
      <PFP name={player?.character_name || "You"} id="PLAYER" />
    </div>
  );
}
