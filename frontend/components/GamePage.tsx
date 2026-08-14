"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import { TopBar } from "./TopBar";
import { ChatContainer } from "./ChatContainer";
import { ActivitySidebar } from "./ActivitySidebar";
import { CharacterInspectorDrawer } from "./CharacterInspectorDrawer";
import { CoachModal } from "./CoachModal";

export function GamePage() {
  const selected = useGameStore((s) => s.selectedCharacterId);
  const coachSkill = useGameStore((s) => s.coachSkill);

  return (
    <div className="flex h-screen flex-col bg-bg">
      <TopBar />
      <div className="relative flex flex-1 overflow-hidden">
        <ChatContainer />
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
      </div>
      <AnimatePresence>{coachSkill && <CoachModal skill={coachSkill} />}</AnimatePresence>
    </div>
  );
}
