"use client";

import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import { LastExchange } from "./LastExchange";

export function MissionLobbyScreen() {
  const mission = useGameStore((s) => s.mission);
  const entries = useGameStore((s) => s.entries);
  const isLoading = useGameStore((s) => s.isLoading);
  const error = useGameStore((s) => s.error);
  const startMission = useGameStore((s) => s.startMission);
  const requestRevision = useGameStore((s) => s.requestRevision);
  const shiftNotice = useGameStore((s) => s.shiftNotice);
  const events = useGameStore((s) => s.events);
  const feasibility = useGameStore((s) => s.feasibility);

  const recap = entries.filter((e) => e.kind === "narration").pop();
  const meanwhile = events.filter((e) => e.startsWith("Meanwhile,")).slice(-2);

  const blocked =
    feasibility && feasibility.blockers.length > 0
      ? feasibility.blockers
      : [];
  const pathSteps = feasibility && feasibility.path.length > 0 ? feasibility.path : [];

  return (
    <div className="min-h-screen bg-bg p-4 sm:p-8">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        {meanwhile.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-edge bg-surface/40 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              Meanwhile
            </p>
            <ul className="mt-1.5 space-y-1">
              {meanwhile.map((e, i) => (
                <li key={`${i}-${e}`} className="text-sm italic text-muted">
                  {e}
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        {shiftNotice && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-shift bg-shift/10 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-shift">World shift</p>
            <p className="mt-1 text-sm text-ink">{shiftNotice}</p>
          </motion.div>
        )}

        {feasibility && feasibility.verdict && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-edge bg-surface/40 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              The world checked your plan
            </p>
            <p className="mt-1.5 text-sm text-ink">{feasibility.verdict}</p>

            {blocked.length > 0 && (
              <ul className="mt-3 space-y-2">
                {blocked.map((b, i) => (
                  <li key={`b-${i}`} className="text-sm">
                    <span className="font-medium text-suspicion">{b.step}</span>
                    <span className="block text-muted">{b.why_blocked}</span>
                    {b.how_to_unlock && (
                      <span className="block text-accent">How to unlock: {b.how_to_unlock}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {pathSteps.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">
                  The possible path
                </p>
                {pathSteps.map((s, i) => (
                  <p key={`p-${i}`} className="text-sm text-ink">
                    {i + 1}. <span className="font-medium">{s.step}</span>
                    {s.reason && <span className="text-muted"> — {s.reason}</span>}
                  </p>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {recap && recap.text && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-edge bg-surface/60 p-4 text-sm italic text-muted"
          >
            {recap.text}
          </motion.div>
        )}

        <LastExchange />

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

          {mission?.reason && (
            <p className="mt-2 rounded-lg border border-edge bg-surface-2/60 px-3 py-2 text-xs text-muted">
              Why this first: {mission.reason}
            </p>
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

          <button
            type="button"
            onClick={requestRevision}
            disabled={isLoading}
            className="mt-3 w-full rounded-lg border border-edge bg-surface px-4 py-2.5 text-sm font-medium text-muted transition hover:text-ink disabled:opacity-50"
          >
            Revise plan
          </button>
        </motion.div>
      </div>
    </div>
  );
}
