"use client";

import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";

export function MissionLobbyScreen() {
  const mission = useGameStore((s) => s.mission);
  const entries = useGameStore((s) => s.entries);
  const isLoading = useGameStore((s) => s.isLoading);
  const error = useGameStore((s) => s.error);
  const startMission = useGameStore((s) => s.startMission);

  const recap = entries.filter((e) => e.kind === "narration").pop();

  return (
    <div className="min-h-screen bg-bg p-4 sm:p-8">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        {recap && recap.text && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-edge bg-surface/60 p-4 text-sm italic text-muted"
          >
            {recap.text}
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-edge bg-surface p-6"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-accent">
              Mission {mission?.id ?? "?"}
            </span>
            <span className="text-xs text-muted">{mission?.chain_progress}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-ink">
            {mission?.title || "No mission"}
          </h1>
          {mission?.description && (
            <p className="mt-2 text-sm text-muted">{mission.description}</p>
          )}

          <dl className="mt-5 space-y-3 text-sm">
            {mission?.location && (
              <div className="flex gap-3">
                <dt className="w-24 shrink-0 font-medium text-muted">Location</dt>
                <dd className="text-ink">{mission.location}</dd>
              </div>
            )}
            {mission?.objective && (
              <div className="flex gap-3">
                <dt className="w-24 shrink-0 font-medium text-muted">Goal</dt>
                <dd className="text-ink">{mission.objective}</dd>
              </div>
            )}
            {mission?.reward && (
              <div className="flex gap-3">
                <dt className="w-24 shrink-0 font-medium text-muted">Reward</dt>
                <dd className="text-ink">{mission.reward}</dd>
              </div>
            )}
            {mission && mission.characters.length > 0 && (
              <div className="flex gap-3">
                <dt className="w-24 shrink-0 font-medium text-muted">In the room</dt>
                <dd className="text-ink">{mission.characters.join(", ")}</dd>
              </div>
            )}
          </dl>

          {error && <p className="mt-3 text-xs text-suspicion">{error}</p>}

          <button
            type="button"
            onClick={startMission}
            disabled={isLoading}
            className="mt-6 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
          >
            {isLoading ? "Entering…" : "Enter Mission"}
          </button>
        </motion.div>
      </div>
    </div>
  );
}
