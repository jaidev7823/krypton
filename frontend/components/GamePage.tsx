"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import { TopBar } from "./TopBar";
import { ChatContainer } from "./ChatContainer";
import { ActivitySidebar } from "./ActivitySidebar";
import { CharacterInspectorDrawer } from "./CharacterInspectorDrawer";
import { CoachChatDrawer } from "./CoachChatDrawer";
import { CoachModal } from "./CoachModal";
import { InputBar } from "./InputBar";

export function GamePage() {
  const selected = useGameStore((s) => s.selectedCharacterId);
  const coachSkill = useGameStore((s) => s.coachSkill);
  const coachOpen = useGameStore((s) => s.coachOpen);
  const gameState = useGameStore((s) => s.gameState);
  const mission = useGameStore((s) => s.mission);
  const sendMessage = useGameStore((s) => s.sendMessage);
  const isLoading = useGameStore((s) => s.isLoading);

  const leaveScene = () => {
    if (!isLoading) {
      void sendMessage("I need to go. See you later.");
    }
  };

  return (
    <div className="flex h-screen flex-col bg-bg">
      <TopBar />
      <div className="relative flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          {gameState === "live_scene" && mission && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="shrink-0 border-b border-accent/30 bg-accent/5 px-4 py-3 sm:px-8"
            >
              <div className="mx-auto max-w-3xl">
                <p className="text-xs font-semibold uppercase tracking-wide text-accent">
                  Mission: {mission.title}
                </p>
                <p className="mt-1 text-sm text-ink">{mission.objective}</p>
                {mission.win_conditions.length > 0 && (
                  <p className="mt-1 text-xs text-muted">
                    Goal: {mission.win_conditions.map((c) => `${c.character} ${c.stat} ${c.min ? `>= ${c.min}` : `<= ${c.max}`}`).join(", ")}
                  </p>
                )}
                {mission.fail_conditions.length > 0 && (
                  <p className="mt-0.5 text-xs text-suspicion/70">
                    Risk: {mission.fail_conditions.map((c) => `${c.character} ${c.stat} ${c.max ? `<= ${c.max}` : `>= ${c.min}`}`).join(", ")}
                  </p>
                )}
              </div>
            </motion.div>
          )}
          <ChatContainer />
          {gameState === "live_scene" && (
            <div className="shrink-0 border-t border-edge bg-surface px-4 py-2 sm:px-8">
              <div className="mx-auto flex max-w-3xl justify-end">
                <button
                  onClick={leaveScene}
                  disabled={isLoading}
                  className="rounded-lg border border-edge bg-surface-2 px-3 py-1.5 text-xs font-medium text-muted transition hover:text-ink disabled:opacity-50"
                >
                  Leave scene
                </button>
              </div>
            </div>
          )}
          <InputBar />
        </div>
        <ActivitySidebar />
        <AnimatePresence>
          {selected && (
            <motion.div
              key="inspector"
              initial={{ x: 420 }}
              animate={{ x: 0 }}
              exit={{ x: 420 }}
              transition={{ type: "spring", damping: 28, stiffness: 260 }}
              className="absolute right-0 top-0 h-full w-80 border-l border-edge bg-surface shadow-2xl"
            >
              <CharacterInspectorDrawer characterId={selected} />
            </motion.div>
          )}
        </AnimatePresence>
        <AnimatePresence>
          {coachOpen && <CoachChatDrawer />}
        </AnimatePresence>
      </div>
      <AnimatePresence>{coachSkill && <CoachModal skill={coachSkill} />}</AnimatePresence>
    </div>
  );
}
