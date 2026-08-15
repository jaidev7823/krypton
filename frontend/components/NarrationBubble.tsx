"use client";

import type { ChatEntry } from "@/lib/types";

export function NarrationBubble({ entry }: { entry: Extract<ChatEntry, { kind: "narration" }> }) {
  return (
    <div className="px-1">
      <p className="text-sm italic leading-relaxed text-muted">{entry.text}</p>
    </div>
  );
}
