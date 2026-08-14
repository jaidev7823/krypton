"use client";

import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";

export function PlanRevisionScreen() {
  const debrief = useGameStore((s) => s.debrief);
  const entries = useGameStore((s) => s.entries);
  const isLoading = useGameStore((s) => s.isLoading);
  const error = useGameStore((s) => s.error);
  const submitNewPlan = useGameStore((s) => s.submitNewPlan);

  const recap = entries.filter((e) => e.kind === "narration").pop();

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const plan = String(data.get("plan") || "").trim();
    if (!plan) return;
    submitNewPlan(plan);
  };

  return (
    <div className="min-h-screen bg-bg p-4 sm:p-8">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        {debrief && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-suspicion/40 bg-suspicion/10 p-4"
          >
            <p className="text-[11px] font-semibold uppercase tracking-wide text-suspicion">
              Your plan fell apart
            </p>
            <p className="mt-2 text-sm text-ink">{debrief.message}</p>
            {(debrief.location || debrief.who_is_around.length > 0) && (
              <p className="mt-2 text-xs text-muted">
                {debrief.location && <>You&apos;re at {debrief.location}.</>}
                {debrief.who_is_around.length > 0 && (
                  <> Around you: {debrief.who_is_around.join(", ")}.</>
                )}
              </p>
            )}
          </motion.div>
        )}

        {!debrief && recap && recap.text && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-edge bg-surface/60 p-4 text-sm italic text-muted"
          >
            {recap.text}
          </motion.div>
        )}

        <motion.form
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={submit}
          className="rounded-2xl border border-edge bg-surface p-6"
        >
          <h1 className="text-xl font-bold tracking-tight text-ink">
            What is your new plan?
          </h1>
          <p className="mt-1 text-sm text-muted">
            The world doesn&apos;t reset. Characters remember what you did — shape a
            plan that works around the damage.
          </p>

          <label className="mt-5 block">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">
              New plan
            </span>
            <textarea
              name="plan"
              placeholder="e.g. Earn back Matsuda's trust before approaching L"
              rows={4}
              className="mt-1 w-full rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent"
            />
          </label>

          {error && <p className="mt-3 text-xs text-suspicion">{error}</p>}

          <button
            type="submit"
            disabled={isLoading}
            className="mt-5 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
          >
            {isLoading ? "Building missions…" : "Set the new plan"}
          </button>
        </motion.form>
      </div>
    </div>
  );
}
