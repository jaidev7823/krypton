"use client";

import { useState } from "react";

export function InnerThought({ text }: { text: string }) {
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="rounded-xl border border-edge bg-surface-2 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted/60">
        Inner thought {!revealed && "· click to reveal"}
      </p>
      <p
        onClick={() => setRevealed(true)}
        className={`mt-1 text-xs italic leading-relaxed text-muted ${
          revealed ? "blur-thought revealed" : "blur-thought"
        }`}
      >
        {text}
      </p>
    </div>
  );
}
