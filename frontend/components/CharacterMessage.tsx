"use client";

import { useEffect, useRef, useState } from "react";
import { useGameStore, ensureAudioPath } from "@/store/useGameStore";
import { PFP } from "./PFP";
import type { ChatEntry, GameTurnCharacter } from "@/lib/types";

export function CharacterMessage({
  entry,
  characters,
}: {
  entry: Extract<ChatEntry, { kind: "message" }>;
  characters: GameTurnCharacter[];
}) {
  const char = characters.find((c) => c.id === entry.speaker);
  const audioMuted = useGameStore((s) => s.audioMuted);
  const audioPaths = useGameStore((s) => s.audioPaths);
  const selectCharacter = useGameStore((s) => s.selectCharacter);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const name = char?.name || entry.speaker;
  const hasAudio = Boolean(audioPaths[`${entry.speaker}:${entry.text.slice(0, 80)}`]);

  // Auto-play character lines when voice is on
  useEffect(() => {
    if (audioMuted) return;
    let cancelled = false;
    (async () => {
      const path = await ensureAudioPath(audioPaths, entry.speaker, entry.text);
      if (cancelled || !path) return;
      audioRef.current = new Audio(`http://localhost:8000${path}`);
      setPlaying(true);
      audioRef.current
        .play()
        .catch(() => setPlaying(false));
      audioRef.current.onended = () => setPlaying(false);
    })();
    return () => {
      cancelled = true;
      audioRef.current?.pause();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioMuted]);

  const play = async () => {
    const path = await ensureAudioPath(audioPaths, entry.speaker, entry.text);
    if (!path) return;
    if (audioRef.current) audioRef.current.pause();
    audioRef.current = new Audio(`http://localhost:8000${path}`);
    setPlaying(true);
    audioRef.current.play().catch(() => setPlaying(false));
    audioRef.current.onended = () => setPlaying(false);
  };

  return (
    <div className="flex items-start gap-3">
      <button onClick={() => selectCharacter(char?.id || entry.speaker)} title="Inspect character">
        <PFP name={name} id={entry.speaker} />
      </button>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <button
            onClick={() => selectCharacter(char?.id || entry.speaker)}
            className="text-xs font-semibold tracking-wide text-ink hover:text-accent"
          >
            {name}
          </button>
          <button
            onClick={play}
            disabled={!hasAudio}
            title={hasAudio ? "Play voice" : "No voice available"}
            className={`text-[11px] transition ${hasAudio ? "text-muted hover:text-accent" : "text-muted/30"}`}
          >
            {playing ? "■" : "▶"}
          </button>
        </div>
        <div className="max-w-full rounded-2xl rounded-tl-sm border border-edge bg-surface-2 px-4 py-3 text-sm leading-relaxed text-ink">
          {entry.text}
        </div>
      </div>
    </div>
  );
}
