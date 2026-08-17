"use client";

import { useState } from "react";
import { useGameStore } from "@/store/useGameStore";

export function InputBar() {
  const gameState = useGameStore((s) => s.gameState);
  const sendMessage = useGameStore((s) => s.sendMessage);
  const declareAction = useGameStore((s) => s.declareAction);
  const isLoading = useGameStore((s) => s.isLoading);
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim() || isLoading) return;
    const value = text;
    setText("");
    if (gameState === "live_scene") {
      void sendMessage(value);
    } else {
      void declareAction(value);
    }
  };

  const isScene = gameState === "live_scene";

  return (
    <div className="shrink-0 border-t border-edge bg-surface px-4 py-3 sm:px-8">
      <div className="mx-auto flex max-w-3xl items-center gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={
            isLoading
              ? "The world is reacting..."
              : isScene
                ? "What do you say or do?"
                : "Describe your next action"
          }
          disabled={isLoading}
          className="flex-1 rounded-xl border border-edge bg-surface-2 px-4 py-2.5 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent disabled:opacity-60"
        />
        <button
          onClick={submit}
          disabled={isLoading || !text.trim()}
          className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
        >
          {isScene ? "Send" : "Go"}
        </button>
      </div>
    </div>
  );
}
