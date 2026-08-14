"use client";

import { useGameStore } from "@/store/useGameStore";
import { PFP } from "./PFP";
import { StatBar } from "./StatBar";
import { MemoryList } from "./MemoryList";
import { InnerThought } from "./InnerThought";

export function CharacterInspectorDrawer({ characterId }: { characterId: string }) {
  const char = useGameStore((s) => s.characters.find((c) => c.id === characterId));
  const entries = useGameStore((s) => s.entries);
  const selectCharacter = useGameStore((s) => s.selectCharacter);

  if (!char) return null;

  const lastThought = [...entries]
    .reverse()
    .find((e) => e.kind === "message" && e.speaker === characterId && e.inner_thought);
  const innerThought = lastThought?.kind === "message" ? lastThought.inner_thought : null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-edge px-4 py-3">
        <div className="flex items-center gap-3">
          <PFP name={char.name} id={char.id} size={40} />
          <div>
            <p className="text-sm font-semibold text-ink">{char.name}</p>
            <p className="text-xs text-muted">{char.id}</p>
          </div>
        </div>
        <button
          onClick={() => selectCharacter(null)}
          className="text-muted transition hover:text-ink"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        <div className="space-y-3">
          <StatBar label="Trust" value={char.stats.trust_towards_player ?? 0} delta={char.stat_deltas.trust} good />
          <StatBar label="Suspicion" value={char.stats.suspicion_towards_player ?? 0} delta={char.stat_deltas.suspicion} good={false} />
          <StatBar label="Stress" value={char.stats.stress ?? 0} delta={char.stat_deltas.stress} good={false} />
        </div>

        {innerThought && <InnerThought text={innerThought} />}

        <div className="space-y-3">
          <div className="rounded-xl border border-edge bg-surface-2 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">
              Current problem
            </p>
            <p className="mt-1 text-sm text-ink">
              {char.current_problem || "—"}
            </p>
          </div>
          <div className="rounded-xl border border-edge bg-surface-2 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">
              Solution
            </p>
            <p className="mt-1 text-sm text-ink">{char.solution || "—"}</p>
          </div>
          <div className="rounded-xl border border-edge bg-surface-2 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">
              Approach
            </p>
            <p className="mt-1 text-sm text-ink">
              {char.problem_solving_framework || "—"}
            </p>
          </div>
        </div>

        <MemoryList memory={char.memory} />
      </div>
    </div>
  );
}
