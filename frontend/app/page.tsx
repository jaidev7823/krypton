"use client";

import { useGameStore } from "@/store/useGameStore";
import { GamePage } from "@/components/GamePage";
import { PlayerSetupScreen } from "@/components/PlayerSetupScreen";

export default function Home() {
  const player = useGameStore((s) => s.player);

  return player ? <GamePage /> : <PlayerSetupScreen />;
}
