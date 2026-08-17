"use client";

import { useGameStore } from "@/store/useGameStore";
import { GamePage } from "@/components/GamePage";
import { WorldScreen } from "@/components/WorldScreen";
import { PlayerSetupScreen } from "@/components/PlayerSetupScreen";

export default function Home() {
  const player = useGameStore((s) => s.player);
  const gameState = useGameStore((s) => s.gameState);

  if (!player || gameState === "setup") return <PlayerSetupScreen />;
  if (gameState === "world") return <WorldScreen />;
  return <GamePage />;
}
