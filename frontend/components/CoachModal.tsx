"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import type { Skill } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function CoachModal({ skill }: { skill: Skill }) {
  const openCoach = useGameStore((s) => s.openCoach);
  const [detail, setDetail] = useState<Skill | null>(skill.definition ? skill : null);
  const [loading, setLoading] = useState(!detail);

  useEffect(() => {
    if (detail) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/skill/${skill.id}`);
        if (res.ok && !cancelled) setDetail((await res.json()) as Skill);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [detail, skill.id]);

  const examples = detail?.example_good ?? [];
  const badExamples = detail?.example_bad ?? [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={() => openCoach(null)}
    >
      <motion.div
        initial={{ scale: 0.96, y: 10 }}
        animate={{ scale: 1, y: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-2xl border border-edge bg-surface p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">Coach</p>
            <h2 className="mt-1 text-xl font-bold text-ink">{skill.id}</h2>
          </div>
          <button
            onClick={() => openCoach(null)}
            className="text-muted transition hover:text-ink"
          >
            ✕
          </button>
        </div>

        {loading && <p className="mt-4 text-sm text-muted">Loading skill…</p>}

        {detail && (
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted/60">Definition</p>
              <p className="mt-1 text-sm leading-relaxed text-ink">{detail.definition}</p>
              {detail.psychology && (
                <p className="mt-1 text-xs text-muted">{detail.psychology}</p>
              )}
            </div>

            {examples.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-trust">Good example</p>
                {examples.map((ex, i) => (
                  <p
                    key={i}
                    className="mt-1 rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-ink"
                  >
                    {typeof ex === "string" ? ex : JSON.stringify(ex)}
                  </p>
                ))}
              </div>
            )}

            {badExamples.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-suspicion">Avoid</p>
                {badExamples.map((ex, i) => (
                  <p
                    key={i}
                    className="mt-1 rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-muted"
                  >
                    {typeof ex === "string" ? ex : JSON.stringify(ex)}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
