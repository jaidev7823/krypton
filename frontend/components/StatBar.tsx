"use client";

import { motion } from "framer-motion";

export function StatBar({
  label,
  value,
  delta,
  good,
}: {
  label: string;
  value: number;
  delta?: number;
  good: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-muted">{label}</span>
        <span className="flex items-center gap-2 text-ink">
          {value}
          {delta !== undefined && delta !== 0 && (
            <motion.span
              key={`${label}-${delta}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={delta > 0 === good ? "text-trust" : "text-suspicion"}
            >
              {delta > 0 ? `+${delta}` : delta}
            </motion.span>
          )}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
        <motion.div
          className={`h-full rounded-full ${good ? "bg-trust" : "bg-suspicion"}`}
          initial={{ width: 0 }}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
