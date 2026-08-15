"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";

const SUGGESTIONS = [
  "Which concept should I use to win?",
  "Why isn't the character trusting me?",
  "What am I doing wrong?",
  "How close am I to winning this mission?",
];

export function CoachChatDrawer() {
  const messages = useGameStore((s) => s.coachMessages);
  const loading = useGameStore((s) => s.coachLoading);
  const askCoach = useGameStore((s) => s.askCoach);
  const toggleCoach = useGameStore((s) => s.toggleCoach);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = (text: string) => {
    const t = text.trim();
    if (!t || loading) return;
    setInput("");
    void askCoach(t);
  };

  return (
    <motion.aside
      initial={{ x: 380 }}
      animate={{ x: 0 }}
      exit={{ x: 380 }}
      transition={{ type: "spring", damping: 28, stiffness: 260 }}
      className="absolute right-0 top-0 flex h-full w-80 flex-col border-l border-edge bg-surface shadow-2xl"
    >
      <div className="flex items-center justify-between border-b border-edge px-4 py-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">Coach</p>
          <p className="text-xs text-muted">Sees your stats & the mission. Ask anything.</p>
        </div>
        <button
          onClick={toggleCoach}
          className="text-muted transition hover:text-ink"
          aria-label="Close coach"
        >
          ✕
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-muted">
              I can read your live stats, the mission&apos;s win conditions, the events happening
              in the world, and the skill book. Ask me what to do next.
            </p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="block w-full rounded-lg border border-edge bg-surface-2 px-3 py-2 text-left text-xs text-muted transition hover:border-accent/50 hover:text-ink"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={`${i}-${m.content.slice(0, 20)}`}
            className={`max-w-[90%] rounded-xl px-3 py-2 text-sm ${
              m.role === "player"
                ? "ml-auto bg-accent text-white"
                : "border border-edge bg-surface-2 text-ink"
            }`}
          >
            {m.content}
          </div>
        ))}

        {loading && (
          <div className="max-w-[90%] rounded-xl border border-edge bg-surface-2 px-3 py-2 text-sm italic text-muted">
            Coach is thinking…
          </div>
        )}
      </div>

      <form
        className="flex gap-2 border-t border-edge p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the coach…"
          className="min-w-0 flex-1 rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="shrink-0 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white transition hover:bg-accent/90 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </motion.aside>
  );
}
