"use client";

import { useGameStore } from "@/store/useGameStore";

export function ChallengeHint() {
  const characters = useGameStore((s) => s.characters);
  const openCoach = useGameStore((s) => s.openCoach);

  const challenges = characters
    .filter((c) => c.challenge_for_player?.required_concept)
    .map((c) => ({
      name: c.name,
      concept: c.challenge_for_player!.required_concept,
      why: c.challenge_for_player!.why,
    }));

  if (challenges.length === 0) return null;

  const openCoachFor = (concept: string) =>
    openCoach({ id: concept, name: concept, definition: "", example_good: [], example_bad: [] });

  return (
    <div className="shrink-0 border-t border-edge bg-surface px-4 pb-2 pt-2 sm:px-8">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2 text-xs text-muted">
        <span className="font-medium uppercase tracking-wide text-muted/60">Expects:</span>
        {challenges.map((c) => (
          <button
            key={c.name}
            onClick={() => openCoachFor(c.concept)}
            className="rounded-full border border-edge bg-surface-2 px-2.5 py-1 text-accent transition hover:border-accent/50"
            title={c.why}
          >
            {c.name} wants {c.concept}
          </button>
        ))}
      </div>
    </div>
  );
}
