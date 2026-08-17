"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";

export function WorldScreen() {
  const isLoading = useGameStore((s) => s.isLoading);
  const error = useGameStore((s) => s.error);
  const feasibility = useGameStore((s) => s.feasibility);
  const sceneHooks = useGameStore((s) => s.sceneHooks);
  const events = useGameStore((s) => s.events);
  const strategicPlan = useGameStore((s) => s.strategicPlan);
  const declareAction = useGameStore((s) => s.declareAction);
  const [text, setText] = useState("");

  const meanwhile = events.filter((e) => e.startsWith("Meanwhile,")).slice(-3);

  const submit = () => {
    if (!text.trim() || isLoading) return;
    const value = text;
    setText("");
    void declareAction(value);
  };

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

        {feasibility && !feasibility.feasible && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-suspicion/40 bg-suspicion/10 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-suspicion">
              That won&apos;t work right now
            </p>
            <p className="mt-1.5 text-sm text-ink">{feasibility.reason}</p>
            {feasibility.suggestions && feasibility.suggestions.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {feasibility.suggestions.map((s, i) => (
                  <li key={i} className="text-sm text-accent">
                    {s}
                  </li>
                ))}
              </ul>
            )}
          </motion.div>
        )}

        {sceneHooks.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-accent/40 bg-accent/10 p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-accent">
              Ideas from the last scene
            </p>
            <ul className="mt-1.5 space-y-1.5">
              {sceneHooks.map((h, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium text-ink">{h.character}:</span>{" "}
                  <span className="text-muted">{h.suggestion}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        {strategicPlan && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-edge bg-surface p-4"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              Your strategic plan
            </p>
            <p className="mt-1.5 text-sm text-ink">{strategicPlan}</p>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-edge bg-surface p-6"
        >
          <h1 className="text-xl font-bold tracking-tight text-ink">
            What do you do next?
          </h1>
          <p className="mt-1 text-sm text-muted">
            Describe your next action. The world will check feasibility and bring the scene to life.
          </p>

          <div className="mt-4 flex gap-2">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder={isLoading ? "Checking feasibility..." : "e.g. Talk to Matsuda in the cafeteria"}
              disabled={isLoading}
              className="flex-1 rounded-xl border border-edge bg-surface-2 px-4 py-2.5 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent disabled:opacity-60"
            />
            <button
              onClick={submit}
              disabled={isLoading || !text.trim()}
              className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
            >
              Go
            </button>
          </div>

          {error && <p className="mt-3 text-xs text-suspicion">{error}</p>}
        </motion.div>
      </div>
    </div>
  );
}
