"use client";

import { useGameStore } from "@/store/useGameStore";
import { PFP } from "./PFP";
import { StatDeltaChips } from "./StatDeltaChips";

// Read-only replay of the final exchange (player words, narration, then each
// character's reply) so the player can actually READ the ending that caused
// the mission to end - the full game chat is hidden behind the mission screens.
export function LastExchange() {
  const entries = useGameStore((s) => s.entries);
  const characters = useGameStore((s) => s.characters);
  const player = useGameStore((s) => s.player);

  const lastNarration = [...entries]
    .reverse()
    .findIndex((e) => e.kind === "narration");
  if (lastNarration === -1) return null;
  const start = entries.length - 1 - lastNarration;
  const exchange = entries.slice(start);

  return (
    <div className="rounded-2xl border border-edge bg-surface p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
        What happened
      </p>
      <div className="mt-3 flex flex-col gap-3">
        {exchange.map((entry) =>
          entry.kind === "narration" ? (
            <p key={entry.id} className="px-1 text-sm italic leading-relaxed text-muted">
              {entry.text}
            </p>
          ) : entry.speaker === "PLAYER" ? (
            <div key={entry.id} className="flex items-start justify-end gap-2">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm border border-accent/40 bg-accent/10 px-3 py-2 text-sm text-ink">
                {entry.text}
              </div>
              <PFP name={player?.character_name || "You"} id="PLAYER" />
            </div>
          ) : (
            <div key={entry.id} className="flex items-start gap-2">
              <PFP name={characters.find((c) => c.id === entry.speaker)?.name || entry.speaker} id={entry.speaker} />
              <div className="min-w-0 max-w-[80%]">
                <p className="mb-0.5 text-[11px] font-semibold text-ink">
                  {characters.find((c) => c.id === entry.speaker)?.name || entry.speaker}
                </p>
                <div className="rounded-2xl rounded-tl-sm border border-edge bg-surface-2 px-3 py-2 text-sm text-ink">
                  {entry.text}
                </div>
                <div className="mt-1">
                  <StatDeltaChips deltas={entry.stat_deltas} />
                </div>
              </div>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
