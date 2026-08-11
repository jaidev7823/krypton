"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import { NarrationBubble } from "./NarrationBubble";
import { CharacterMessage } from "./CharacterMessage";
import { PlayerMessage } from "./PlayerMessage";
import { ChallengeHint } from "./ChallengeHint";
import { InputBar } from "./InputBar";

export function ChatContainer() {
  const entries = useGameStore((s) => s.entries);
  const isLoading = useGameStore((s) => s.isLoading);
  const characters = useGameStore((s) => s.characters);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries, isLoading]);

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {entries.length === 0 && !isLoading && (
            <p className="mt-16 text-center text-sm text-muted">
              You are now in the world. Say or do anything — the world will react.
            </p>
          )}
          <AnimatePresence initial={false}>
            {entries.map((entry) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                {entry.kind === "narration" ? (
                  <NarrationBubble entry={entry} />
                ) : entry.speaker === "PLAYER" ? (
                  <PlayerMessage entry={entry} />
                ) : (
                  <CharacterMessage entry={entry} characters={characters} />
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {isLoading && (
            <div className="flex items-center gap-2 px-2 text-xs text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              the world is thinking…
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>
      <ChallengeHint />
      <InputBar />
    </div>
  );
}
