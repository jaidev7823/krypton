"use client";

import { useGameStore } from "@/store/useGameStore";
import { GamePage } from "@/components/GamePage";
import { MissionLobbyScreen } from "@/components/MissionLobbyScreen";
import { PlayerSetupScreen } from "@/components/PlayerSetupScreen";
import { PlanRevisionScreen } from "@/components/PlanRevisionScreen";

export default function Home() {
  const player = useGameStore((s) => s.player);
  const gameState = useGameStore((s) => s.gameState);
  const mission = useGameStore((s) => s.mission);

  if (!player || gameState === "plan_elicitation") return <PlayerSetupScreen />;
  if (gameState === "plan_revision") return <PlanRevisionScreen />;
  if (gameState === "mission_lobby") return <MissionLobbyScreen />;
  if (gameState === "complete") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg p-4">
        <div className="w-full max-w-lg rounded-2xl border border-edge bg-surface p-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            Your plan is complete
          </h1>
          <p className="mt-3 text-sm text-muted">
            {mission?.title
              ? `The world changed with you. Chain progress: ${mission.chain_progress}.`
              : "Every mission has been fulfilled. The world remembers what you did."}
          </p>
        </div>
      </div>
    );
  }
  return <GamePage />;
}
