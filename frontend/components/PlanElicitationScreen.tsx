"use client";

import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import { StatBar } from "./StatBar";

export function PlanElicitationScreen() {
  const player = useGameStore((s) => s.player);
  const world = useGameStore((s) => s.world);
  const isLoading = useGameStore((s) => s.isLoading);
  const error = useGameStore((s) => s.error);
  const submitPlayerPlan = useGameStore((s) => s.submitPlayerPlan);

  if (!player) return null;
  const characters = world?.autonomous_players ?? [];

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const plan = String(data.get("plan") || "").trim();
    if (!plan) return;
    submitPlayerPlan(plan);
  };

  return (
    <div className="min-h-screen bg-bg p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-edge bg-surface p-6"
        >
          <h1 className="text-xl font-bold tracking-tight text-ink">
            You are {player.character_name} in {player.world_choice || "the world"}
          </h1>
          <p className="mt-1 text-sm text-muted">Your goal: {player.goal}</p>
        </motion.div>

        <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-muted">
          Who you might cross paths with
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {characters.map((c) => (
            <div key={c.id} className="rounded-xl border border-edge bg-surface p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-ink">
                  {c.canon_name || c.id}
                </span>
                <span className="text-xs text-muted">{c.role}</span>
              </div>
              <p className="mt-2 text-xs text-muted">{c.goal}</p>
              <div className="mt-3 space-y-1.5">
                <StatBar label="Trust" value={c.stats.trust_towards_player} good />
                <StatBar label="Suspicion" value={c.stats.suspicion_towards_player} good={false} />
                <StatBar label="Stress" value={c.stats.stress} good={false} />
              </div>
            </div>
          ))}
          {characters.length === 0 && (
            <p className="text-sm text-muted">World data unavailable.</p>
          )}
        </div>

        <motion.form
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={submit}
          className="mt-8 rounded-2xl border border-edge bg-surface p-6"
        >
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Your plan
          </h3>
          <p className="mt-2 text-sm text-ink">
            How will you achieve your goal: <span className="text-accent">{player.goal}</span>?
            What&apos;s your plan? (e.g. &quot;Join L&apos;s team, then betray him&quot;)
          </p>
          <textarea
            name="plan"
            rows={3}
            placeholder="Break into the investigation slowly. First get close to Matsuda, earn L's attention, find Light's secret..."
            className="mt-3 w-full rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent"
          />
          {error && <p className="mt-2 text-xs text-suspicion">{error}</p>}
          <button
            type="submit"
            disabled={isLoading}
            className="mt-4 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
          >
            {isLoading ? "Designing your missions…" : "Commit to your plan"}
          </button>
        </motion.form>
      </div>
    </div>
  );
}
