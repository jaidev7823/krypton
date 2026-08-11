"use client";

import type { ChatEntry } from "@/lib/types";

export function NarrationBubble({ entry }: { entry: Extract<ChatEntry, { kind: "narration" }> }) {
  return (
    <div className="px-1">
      <p className="text-sm italic leading-relaxed text-muted">{entry.text}</p>
      <div className="mt-1 flex items-center gap-3 text-[11px] uppercase tracking-wide text-muted/60">
        <span>{entry.where}</span>
        <span className="text-edge">|</span>
        <span>{entry.why_here}</span>
      </div>
    </div>
  );
}
