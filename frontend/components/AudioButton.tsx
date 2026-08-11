"use client";

import { useGameStore } from "@/store/useGameStore";

export function AudioButton() {
  const audioMuted = useGameStore((s) => s.audioMuted);
  const toggleAudio = useGameStore((s) => s.toggleAudio);

  return (
    <button
      onClick={toggleAudio}
      title={audioMuted ? "Unmute voices" : "Mute voices"}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
        audioMuted
          ? "border-edge bg-surface-2 text-muted"
          : "border-accent/40 bg-accent/10 text-accent"
      }`}
    >
      {audioMuted ? "MUTED" : "VOICE"}
    </button>
  );
}
