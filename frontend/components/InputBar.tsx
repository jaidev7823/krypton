"use client";

import { useState } from "react";
import { useGameStore } from "@/store/useGameStore";

export function InputBar() {
  const sendMessage = useGameStore((s) => s.sendMessage);
  const isLoading = useGameStore((s) => s.isLoading);
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim() || isLoading) return;
    const value = text;
    setText("");
    void sendMessage(value);
  };

  return (
    <div className="shrink-0 border-t border-edge bg-surface px-4 py-3 sm:px-8">
      <div className="mx-auto flex max-w-3xl items-center gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={isLoading ? "The world is reacting…" : "What do you say or do?"}
          disabled={isLoading}
          className="flex-1 rounded-xl border border-edge bg-surface-2 px-4 py-2.5 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent disabled:opacity-60"
        />
        <button
          onClick={submit}
          disabled={isLoading || !text.trim()}
          className="rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
